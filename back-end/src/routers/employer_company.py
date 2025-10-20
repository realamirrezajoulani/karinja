from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import Company
from schemas.relational_schemas import RelationalCompanyPublic
from sqlmodel import and_, not_, or_, select
from sqlalchemy.exc import IntegrityError

from schemas.employer_company import CompanyCreate, CompanyUpdate
from utilities.enumerables import EmployerCompanyEmployeeCount, EmployerCompanyIndustry, EmployerCompanyOwnershipType, LogicalOperator, UserAccountStatus, UserRole


router = APIRouter()


@router.get(
    "/employer_companies/",
    response_model=list[RelationalCompanyPublic],
)
async def get_employer_companies(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    company_query = select(Company).offset(offset).limit(limit).order_by(Company.created_at)
    company = await session.exec(company_query)
    return company.all()


@router.post(
    "/employer_companies/",
    response_model=RelationalCompanyPublic,
)
async def create_employer_company(
        *,
        session: AsyncSession = Depends(get_session),
        company_create: CompanyCreate,
):
    try:
        db_company = Company(
            registration_number=company_create.registration_number,
            full_name=company_create.full_name,
            summary=company_create.summary,
            industry=company_create.industry,
            ownership_type=company_create.ownership_type,
            website_address=company_create.website_address,
            founded_year=company_create.founded_year,
            employee_count=company_create.employee_count,
            address=company_create.address,
            phone=company_create.phone,
            description=company_create.description,
            user_id=company_create.user_id,
        )

        session.add(db_company)
        await session.commit()
        await session.refresh(db_company)

        return db_company

    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="کد اقتصادی یا شماره تلفن قبلا ثبت شده است"
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد شرکت: "
        )


@router.get(
    "/employer_companies/{company_id}",
    response_model=RelationalCompanyPublic,
)
async def get_employer_company(
        *,
        session: AsyncSession = Depends(get_session),
        company_id: UUID,
):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="شرکت پیدا نشد")

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
):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="شرکت پیدا نشد")

    update_data = company_update.model_dump(exclude_unset=True)

    company.sqlmodel_update(update_data)

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
):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="شرکت پیدا نشد")

    await session.delete(company)
    await session.commit()

    return {"msg": "شرکت با موفقیت حذف شد"}


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
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if registration_number:
        conditions.append(Company.registration_number == registration_number)
    if full_name:
        conditions.append(Company.full_name.ilike(f"%{full_name}%"))
    if summary:
        conditions.append(Company.summary.ilike(f"%{summary}%"))
    if industry:
        conditions.append(Company.industry == industry)
    if ownership_type:
        conditions.append(Company.ownership_type == ownership_type)
    if founded_year:
        conditions.append(Company.founded_year == founded_year)
    if employee_count:
        conditions.append(Company.employee_count == employee_count)
    if address:
        conditions.append(Company.address.ilike(f"%{address}%"))
    if phone:
        conditions.append(Company.phone == phone)
    if description:
        conditions.append(Company.description.ilike(f"%{description}%"))

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(Company).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(Company).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(Company).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    employer_companies = result.all()
    if not employer_companies:
        raise HTTPException(status_code=404, detail="شرکت پیدا نشد")

    return employer_companies
