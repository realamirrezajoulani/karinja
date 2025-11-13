from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import Company, User
from schemas.relational_schemas import RelationalCompanyPublic
from sqlmodel import and_, not_, or_, select
from sqlalchemy.exc import IntegrityError

from schemas.employer_company import CompanyCreate, CompanyUpdate
from utilities.enumerables import EmployerCompanyEmployeeCount, EmployerCompanyIndustry, EmployerCompanyOwnershipType, LogicalOperator, UserRole
from utilities.authentication import oauth2_scheme


router = APIRouter()


# Roles allowed to READ (JobSeeker included)
READ_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
        UserRole.JOB_SEEKER.value,
    )
)

# Roles allowed to WRITE (Employer allowed but only for own companies)
WRITE_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
    )
)


@router.get(
    "/employer_companies/",
    response_model=list[RelationalCompanyPublic],
)
async def get_employer_companies(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    # _user: dict = READ_ROLE_DEP,
    # _: str = Depends(oauth2_scheme),
):
    """
    list companies.
    - FULL_ADMIN / ADMIN: see all companies
    - EMPLOYER: read all companies (write actions restricted to own companies)
    - JOB_SEEKER: read-only
    """
    stmt = (
        select(Company)
        .order_by(Company.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/employer_companies/",
    response_model=RelationalCompanyPublic,
)
async def create_employer_company(
    *,
    session: AsyncSession = Depends(get_session),
    company_create: CompanyCreate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Create a company.
    - EMPLOYER: company.user_id will be forced to requester (they become owner)
    - ADMIN / FULL_ADMIN: can create for any user_id (validated)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    # Determine safe target user_id
    if requester_role == UserRole.EMPLOYER.value:
        target_user_id = requester_id
    else:
        # ADMIN / FULL_ADMIN: use client-provided user_id but validate
        if not company_create.user_id:
            raise HTTPException(status_code=400, detail="user_id is required for admins")
        target_user_id = company_create.user_id
        target_user = await session.get(User, target_user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")

    # Normalize enums if needed
    industry_val = company_create.industry.value if hasattr(company_create.industry, "value") else company_create.industry
    ownership_val = company_create.ownership_type.value if hasattr(company_create.ownership_type, "value") else company_create.ownership_type
    employee_count_val = company_create.employee_count.value if hasattr(company_create.employee_count, "value") else company_create.employee_count

    try:
        db_company = Company(
            registration_number=company_create.registration_number,
            full_name=company_create.full_name,
            summary=company_create.summary,
            industry=industry_val,
            ownership_type=ownership_val,
            website_address=company_create.website_address,
            founded_year=company_create.founded_year,
            employee_count=employee_count_val,
            address=company_create.address,
            phone=company_create.phone,
            description=company_create.description,
            user_id=target_user_id,
        )

        session.add(db_company)
        await session.commit()
        await session.refresh(db_company)

        return db_company

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Unique constraint violated (registration_number or phone may be duplicated)")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating company: {e}")


@router.get(
    "/employer_companies/{company_id}",
    response_model=RelationalCompanyPublic,
)
async def get_employer_company(
    *,
    session: AsyncSession = Depends(get_session),
    company_id: UUID,
    # _user: dict = READ_ROLE_DEP,
    # _: str = Depends(oauth2_scheme),
):
    """
    Retrieve a single company.
    - Everyone with read permission can retrieve (JobSeeker and Employer see any company)
    """
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.patch(
    "/employer_companies/{company_id}",
    response_model=RelationalCompanyPublic,
)
async def patch_employer_company(
    *,
    session: AsyncSession = Depends(get_session),
    company_id: UUID,
    company_update: CompanyUpdate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Update a company.
    - FULL_ADMIN / ADMIN: can update any company (may change user_id)
    - EMPLOYER: can update only companies they own; cannot change user_id
    - JOB_SEEKER: no write access
    """
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    # Employer ownership check
    if requester_role == UserRole.EMPLOYER.value:
        if str(company.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="You can only modify companies you own")

    update_data = company_update.model_dump(exclude_unset=True)

    # Prevent employers from reassigning ownership
    if requester_role == UserRole.EMPLOYER.value and "user_id" in update_data:
        raise HTTPException(status_code=403, detail="You cannot change the owner of the company")

    # If admin changed user_id, validate target user exists
    if "user_id" in update_data:
        new_user = await session.get(User, update_data["user_id"])
        if not new_user:
            raise HTTPException(status_code=404, detail="Target user not found")

    # Normalize enums if present
    if "industry" in update_data and hasattr(update_data["industry"], "value"):
        update_data["industry"] = update_data["industry"].value
    if "ownership_type" in update_data and hasattr(update_data["ownership_type"], "value"):
        update_data["ownership_type"] = update_data["ownership_type"].value
    if "employee_count" in update_data and hasattr(update_data["employee_count"], "value"):
        update_data["employee_count"] = update_data["employee_count"].value

    # Apply updates
    for field, value in update_data.items():
        setattr(company, field, value)

    await session.commit()
    await session.refresh(company)
    return company


@router.delete(
    "/employer_companies/{company_id}",
    response_model=dict[str, str],
)
async def delete_employer_company(
    *,
    session: AsyncSession = Depends(get_session),
    company_id: UUID,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete a company.
    - FULL_ADMIN / ADMIN: can delete any company
    - EMPLOYER: can delete only companies they own
    """
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.EMPLOYER.value:
        if str(company.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="You can only delete companies you own")

    await session.delete(company)
    await session.commit()
    return {"msg": "Company deleted successfully"}


@router.get(
    "/employer_companies/search/",
    response_model=list[RelationalCompanyPublic],
)
async def search_employer_companies(
    *,
    session: AsyncSession = Depends(get_session),
    registration_number: str | None = None,
    full_name: str | None = None,
    summary: str | None = None,
    industry: EmployerCompanyIndustry | None = None,
    ownership_type: EmployerCompanyOwnershipType | None = None,
    founded_year: int | None = None,
    employee_count: EmployerCompanyEmployeeCount | None = None,
    address: str | None = None,
    phone: str | None = None,
    description: str | None = None,
    operator: LogicalOperator = Query(
        default=LogicalOperator.AND,
        description="Logical operator to combine filters: AND | OR | NOT (NOT interpreted as NOT(OR(...)))",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Search companies.
    - FULL_ADMIN / ADMIN / EMPLOYER / JOB_SEEKER: all can search (employers have additional write privileges elsewhere)
    - NOT interpreted as NOT(OR(...))
    """
    conditions = []
    if registration_number is not None:
        conditions.append(Company.registration_number == registration_number)
    if full_name:
        conditions.append(Company.full_name.ilike(f"%{full_name}%"))
    if summary:
        conditions.append(Company.summary.ilike(f"%{summary}%"))
    if industry is not None:
        ind = industry.value if hasattr(industry, "value") else industry
        conditions.append(Company.industry == ind)
    if ownership_type is not None:
        ot = ownership_type.value if hasattr(ownership_type, "value") else ownership_type
        conditions.append(Company.ownership_type == ot)
    if founded_year is not None:
        conditions.append(Company.founded_year == founded_year)
    if employee_count is not None:
        ec = employee_count.value if hasattr(employee_count, "value") else employee_count
        conditions.append(Company.employee_count == ec)
    if address:
        conditions.append(Company.address.ilike(f"%{address}%"))
    if phone:
        conditions.append(Company.phone == phone)
    if description:
        conditions.append(Company.description.ilike(f"%{description}%"))

    if not conditions:
        raise HTTPException(status_code=400, detail="No search filters provided")

    # Combine conditions according to operator
    if operator == LogicalOperator.AND:
        where_clause = and_(*conditions)
    elif operator == LogicalOperator.OR:
        where_clause = or_(*conditions)
    elif operator == LogicalOperator.NOT:
        # interpret NOT as NOT(OR(...))
        where_clause = not_(or_(*conditions))
    else:
        raise HTTPException(status_code=400, detail="Invalid logical operator")

    stmt = (
        select(Company)
        .where(where_clause)
        .order_by(Company.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()

# @router.get(
#     "/employer_companies/",
#     response_model=list[RelationalCompanyPublic],
# )
# async def get_employer_companies(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     company_query = select(Company).offset(offset).limit(limit).order_by(Company.created_at)
#     company = await session.exec(company_query)
#     return company.all()


# @router.post(
#     "/employer_companies/",
#     response_model=RelationalCompanyPublic,
# )
# async def create_employer_company(
#         *,
#         session: AsyncSession = Depends(get_session),
#         company_create: CompanyCreate,
# ):
#     try:
#         db_company = Company(
#             registration_number=company_create.registration_number,
#             full_name=company_create.full_name,
#             summary=company_create.summary,
#             industry=company_create.industry,
#             ownership_type=company_create.ownership_type,
#             website_address=company_create.website_address,
#             founded_year=company_create.founded_year,
#             employee_count=company_create.employee_count,
#             address=company_create.address,
#             phone=company_create.phone,
#             description=company_create.description,
#             user_id=company_create.user_id,
#         )

#         session.add(db_company)
#         await session.commit()
#         await session.refresh(db_company)

#         return db_company

#     except IntegrityError as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=409,
#             detail="کد اقتصادی یا شماره تلفن قبلا ثبت شده است"
#         )
#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد شرکت: "
#         )


# @router.get(
#     "/employer_companies/{company_id}",
#     response_model=RelationalCompanyPublic,
# )
# async def get_employer_company(
#         *,
#         session: AsyncSession = Depends(get_session),
#         company_id: UUID,
# ):
#     company = await session.get(Company, company_id)
#     if not company:
#         raise HTTPException(status_code=404, detail="شرکت پیدا نشد")

#     return company


# @router.patch(
#     "/employer_companies/{company_id}",
#     response_model=RelationalCompanyPublic,
# )
# async def patch_employer_company(
#         *,
#         session: AsyncSession = Depends(get_session),
#         company_id: UUID,
#         company_update: CompanyUpdate,
# ):
#     company = await session.get(Company, company_id)
#     if not company:
#         raise HTTPException(status_code=404, detail="شرکت پیدا نشد")

#     update_data = company_update.model_dump(exclude_unset=True)

#     company.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(company)

#     return company


# @router.delete(
#     "/employer_companies/{company_id}",
#     response_model=dict[str, str],
# )
# async def delete_employer_company(
#     *,
#     session: AsyncSession = Depends(get_session),
#     company_id: UUID,
# ):
#     company = await session.get(Company, company_id)
#     if not company:
#         raise HTTPException(status_code=404, detail="شرکت پیدا نشد")

#     await session.delete(company)
#     await session.commit()

#     return {"msg": "شرکت با موفقیت حذف شد"}


# @router.get(
#     "/employer_companies/search/",
#     response_model=list[RelationalCompanyPublic],
# )
# async def search_employer_companies(
#         *,
#         session: AsyncSession = Depends(get_session),
#         registration_number: str | None = None,
#         full_name: str | None = None,
#         summary: str | None = None,
#         industry: EmployerCompanyIndustry | None = None,
#         ownership_type: EmployerCompanyOwnershipType | None = None,
#         founded_year: int | None = None,
#         employee_count: EmployerCompanyEmployeeCount | None = None,
#         address: str | None = None,
#         phone: str | None = None,
#         description: str | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if registration_number:
#         conditions.append(Company.registration_number == registration_number)
#     if full_name:
#         conditions.append(Company.full_name.ilike(f"%{full_name}%"))
#     if summary:
#         conditions.append(Company.summary.ilike(f"%{summary}%"))
#     if industry:
#         conditions.append(Company.industry == industry)
#     if ownership_type:
#         conditions.append(Company.ownership_type == ownership_type)
#     if founded_year:
#         conditions.append(Company.founded_year == founded_year)
#     if employee_count:
#         conditions.append(Company.employee_count == employee_count)
#     if address:
#         conditions.append(Company.address.ilike(f"%{address}%"))
#     if phone:
#         conditions.append(Company.phone == phone)
#     if description:
#         conditions.append(Company.description.ilike(f"%{description}%"))

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(Company).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(Company).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(Company).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     employer_companies = result.all()
#     if not employer_companies:
#         raise HTTPException(status_code=404, detail="شرکت پیدا نشد")

#     return employer_companies
