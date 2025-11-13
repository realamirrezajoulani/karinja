from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import Company, JobPosting, User
from schemas.relational_schemas import RelationalJobPostingPublic
from sqlmodel import and_, not_, or_, select

from schemas.job_posting import JobPostingCreate, JobPostingUpdate
from utilities.enumerables import IranProvinces, JobPostingEmploymentType, JobPostingJobCategory, JobPostingSalaryUnit, JobPostingStatus, LogicalOperator, UserRole
from utilities.authentication import oauth2_scheme


router = APIRouter()


# Roles allowed to READ (JobSeekers and Employers included)
READ_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
        UserRole.JOB_SEEKER.value,
    )
)

# Roles allowed to WRITE (Employer allowed but only for own company)
WRITE_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
    )
)


@router.get(
    "/job_postings/",
    response_model=list[RelationalJobPostingPublic],
)
async def get_job_postings(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    # _user: dict = READ_ROLE_DEP,
    # _: str = Depends(oauth2_scheme),
):
    """
    list job postings.
    - FULL_ADMIN / ADMIN: see all postings
    - EMPLOYER: read all postings (write restricted to own company for create/patch/delete)
    - JOB_SEEKER: read-only
    """
    # simple listing (no extra visibility restriction for read)
    stmt = (
        select(JobPosting)
        .order_by(JobPosting.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/job_postings/",
    response_model=RelationalJobPostingPublic,
)
async def create_job_posting(
    *,
    session: AsyncSession = Depends(get_session),
    job_posting_create: JobPostingCreate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Create job posting.
    - FULL_ADMIN / ADMIN: can create posting for any company_id (validated to exist)
    - EMPLOYER: can only create postings for their own company (company_id overridden/validated)
    - JOB_SEEKER: not allowed (write excluded)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    # normalize enum-like fields if present
    employment_type = (
        job_posting_create.employment_type.value
        if hasattr(job_posting_create.employment_type, "value")
        else job_posting_create.employment_type
    )
    salary_unit = (
        job_posting_create.salary_unit.value
        if hasattr(job_posting_create.salary_unit, "value")
        else job_posting_create.salary_unit
    )
    job_categoriy = (
        job_posting_create.job_categoriy.value
        if hasattr(job_posting_create.job_categoriy, "value")
        else job_posting_create.job_categoriy
    )
    status = (
        job_posting_create.status.value
        if hasattr(job_posting_create.status, "value")
        else job_posting_create.status
    )

    # Determine target company_id with server-side checks
    target_company_id = job_posting_create.company_id

    if requester_role == UserRole.EMPLOYER.value:
        # ensure employer has an associated company and only allow that company
        employer_user = await session.get(User, requester_id)
        if not employer_user:
            raise HTTPException(status_code=404, detail="Requester user not found")
        # assume User has company_id attribute (adjust if different)
        employer_company_id = getattr(employer_user, "company_id", None)
        if not employer_company_id:
            raise HTTPException(status_code=403, detail="Employer user has no associated company")
        # enforce employer can only create for own company
        target_company_id = employer_company_id
    else:
        # ADMIN / FULL_ADMIN: validate company exists if provided
        if target_company_id is None:
            raise HTTPException(status_code=400, detail="company_id is required")
        company = await session.get(Company, target_company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Target company not found")

    try:
        db_job_posting = JobPosting(
            title=job_posting_create.title,
            location=job_posting_create.location,
            job_description=job_posting_create.job_description,
            employment_type=employment_type,
            posted_date=job_posting_create.posted_date,
            expiry_date=job_posting_create.expiry_date,
            salary_unit=salary_unit,
            salary_range=job_posting_create.salary_range,
            job_categoriy=job_categoriy,
            vacancy_count=job_posting_create.vacancy_count,
            status=status,
            company_id=target_company_id,
        )

        session.add(db_job_posting)
        await session.commit()
        await session.refresh(db_job_posting)

        return db_job_posting

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating job posting: {e}")


@router.get(
    "/job_postings/{job_posting_id}",
    response_model=RelationalJobPostingPublic,
)
async def get_job_posting(
    *,
    session: AsyncSession = Depends(get_session),
    job_posting_id: UUID,
    # _user: dict = READ_ROLE_DEP,
    # _: str = Depends(oauth2_scheme),
):
    """
    Retrieve single job posting (read allowed to all roles).
    - No special restriction for reading: Employers/JobSeekers can read any posting.
    """
    job_posting = await session.get(JobPosting, job_posting_id)
    if not job_posting:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return job_posting


@router.patch(
    "/job_postings/{job_posting_id}",
    response_model=RelationalJobPostingPublic,
)
async def patch_job_posting(
    *,
    session: AsyncSession = Depends(get_session),
    job_posting_id: UUID,
    job_posting_update: JobPostingUpdate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Update a job posting.
    - FULL_ADMIN / ADMIN: can update any posting (may change company_id)
    - EMPLOYER: can update only postings belonging to their own company (cannot change company_id to another)
    - JOB_SEEKER: not allowed (write excluded)
    """
    job_posting = await session.get(JobPosting, job_posting_id)
    if not job_posting:
        raise HTTPException(status_code=404, detail="Job posting not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    # If employer, verify ownership of posting via company_id
    if requester_role == UserRole.EMPLOYER.value:
        employer_user = await session.get(User, requester_id)
        if not employer_user:
            raise HTTPException(status_code=404, detail="Requester user not found")
        employer_company_id = getattr(employer_user, "company_id", None)
        if not employer_company_id:
            raise HTTPException(status_code=403, detail="Employer user has no associated company")
        if str(job_posting.company_id) != str(employer_company_id):
            raise HTTPException(status_code=403, detail="You can only modify job postings of your own company")

    update_data = job_posting_update.model_dump(exclude_unset=True)

    # Prevent employer from reassigning posting to another company
    if requester_role == UserRole.EMPLOYER.value and "company_id" in update_data:
        # ignore or reject: here we reject explicitly
        raise HTTPException(status_code=403, detail="You cannot change company_id of this posting")

    # If ADMIN/FULL_ADMIN changed company_id, validate the company exists
    if "company_id" in update_data:
        new_company = await session.get(Company, update_data["company_id"])
        if not new_company:
            raise HTTPException(status_code=404, detail="Target company not found")

    # Normalize enum-like fields if provided
    enum_fields = ["employment_type", "salary_unit", "job_categoriy", "status"]
    for ef in enum_fields:
        if ef in update_data and hasattr(update_data[ef], "value"):
            update_data[ef] = update_data[ef].value

    # Apply updates
    for field, value in update_data.items():
        setattr(job_posting, field, value)

    await session.commit()
    await session.refresh(job_posting)
    return job_posting


@router.delete(
    "/job_postings/{job_posting_id}",
    response_model=dict[str, str],
)
async def delete_job_posting(
    *,
    session: AsyncSession = Depends(get_session),
    job_posting_id: UUID,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete a job posting.
    - FULL_ADMIN / ADMIN: can delete any posting
    - EMPLOYER: can delete only postings of their own company
    - JOB_SEEKER: not allowed
    """
    job_posting = await session.get(JobPosting, job_posting_id)
    if not job_posting:
        raise HTTPException(status_code=404, detail="Job posting not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.EMPLOYER.value:
        employer_user = await session.get(User, requester_id)
        if not employer_user:
            raise HTTPException(status_code=404, detail="Requester user not found")
        employer_company_id = getattr(employer_user, "company_id", None)
        if not employer_company_id:
            raise HTTPException(status_code=403, detail="Employer user has no associated company")
        if str(job_posting.company_id) != str(employer_company_id):
            raise HTTPException(status_code=403, detail="You can only delete job postings of your own company")

    await session.delete(job_posting)
    await session.commit()
    return {"msg": "Job posting deleted successfully"}


@router.get(
    "/job_postings/search/",
    response_model=list[RelationalJobPostingPublic],
)
async def search_job_postings(
    *,
    session: AsyncSession = Depends(get_session),
    title: str | None = None,
    location: IranProvinces | None = None,
    job_description: str | None = None,
    employment_type: JobPostingEmploymentType | None = None,
    posted_date: str | None = None,
    expiry_date: str | None = None,
    salary_unit: JobPostingSalaryUnit | None = None,
    salary_range: int | None = None,
    job_categoriy: JobPostingJobCategory | None = None,
    vacancy_count: int | None = None,
    status: JobPostingStatus | None = None,
    operator: LogicalOperator = Query(
        default=LogicalOperator.AND,
        description="Logical operator to combine filters: AND | OR | NOT",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Search job postings.
    - FULL_ADMIN / ADMIN / EMPLOYER / JOB_SEEKER: all can search (write rules apply elsewhere)
    - NOT interpreted as NOT(OR(...))
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if title:
        conditions.append(JobPosting.title.ilike(f"%{title}%"))
    if location is not None:
        val = location.value if hasattr(location, "value") else location
        conditions.append(JobPosting.location == val)
    if job_description:
        conditions.append(JobPosting.job_description.ilike(f"%{job_description}%"))
    if employment_type is not None:
        et = employment_type.value if hasattr(employment_type, "value") else employment_type
        conditions.append(JobPosting.employment_type == et)
    if posted_date is not None:
        conditions.append(JobPosting.posted_date == posted_date)
    if expiry_date is not None:
        conditions.append(JobPosting.expiry_date == expiry_date)
    if salary_unit is not None:
        su = salary_unit.value if hasattr(salary_unit, "value") else salary_unit
        conditions.append(JobPosting.salary_unit == su)
    if salary_range is not None:
        conditions.append(JobPosting.salary_range == salary_range)
    if job_categoriy is not None:
        jc = job_categoriy.value if hasattr(job_categoriy, "value") else job_categoriy
        conditions.append(JobPosting.job_categoriy == jc)
    if vacancy_count is not None:
        conditions.append(JobPosting.vacancy_count == vacancy_count)
    if status is not None:
        st = status.value if hasattr(status, "value") else status
        conditions.append(JobPosting.status == st)

    if not conditions:
        raise HTTPException(status_code=400, detail="No search filters provided")

    # Combine conditions according to operator
    if operator == LogicalOperator.AND:
        where_clause = and_(*conditions)
    elif operator == LogicalOperator.OR:
        where_clause = or_(*conditions)
    elif operator == LogicalOperator.NOT:
        where_clause = not_(or_(*conditions))
    else:
        raise HTTPException(status_code=400, detail="Invalid logical operator")

    # For read/search, employers and jobseekers can read all postings (per requirement).
    # No extra restriction applied here; ownership is enforced on write operations.

    stmt = (
        select(JobPosting)
        .where(where_clause)
        .order_by(JobPosting.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()


# @router.get(
#     "/job_postings/",
#     response_model=list[RelationalJobPostingPublic],
# )
# async def get_job_postings(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     job_postings_query = select(JobPosting).offset(offset).limit(limit).order_by(JobPosting.created_at)
#     job_postings = await session.exec(job_postings_query)
#     return job_postings.all()


# @router.post(
#     "/job_postings/",
#     response_model=RelationalJobPostingPublic,
# )
# async def create_job_posting(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_posting_create: JobPostingCreate,
# ):
#     try:
#         db_job_posting = JobPosting(
#             title=job_posting_create.title,
#             location=job_posting_create.location,
#             job_description=job_posting_create.job_description,
#             employment_type=job_posting_create.employment_type,
#             posted_date=job_posting_create.posted_date,
#             expiry_date=job_posting_create.expiry_date,
#             salary_unit=job_posting_create.salary_unit,
#             salary_range=job_posting_create.salary_range,
#             job_categoriy=job_posting_create.job_categoriy,
#             vacancy_count=job_posting_create.vacancy_count,
#             status=job_posting_create.status,
#             company_id=job_posting_create.company_id
#         )

#         session.add(db_job_posting)
#         await session.commit()
#         await session.refresh(db_job_posting)

#         return db_job_posting

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد آگهی شغلی: "
#         )


# @router.get(
#     "/job_postings/{job_posting_id}",
#     response_model=RelationalJobPostingPublic,
# )
# async def get_job_posting(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_posting_id: UUID,
# ):
#     job_posting = await session.get(JobPosting, job_posting_id)
#     if not job_posting:
#         raise HTTPException(status_code=404, detail="آگهی شغلی پیدا نشد")

#     return job_posting


# @router.patch(
#     "/job_postings/{job_posting_id}",
#     response_model=RelationalJobPostingPublic,
# )
# async def patch_job_posting(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_posting_id: UUID,
#         job_posting_update: JobPostingUpdate,
# ):
#     job_posting = await session.get(JobPosting, job_posting_id)
#     if not job_posting:
#         raise HTTPException(status_code=404, detail="آگهی شغلی پیدا نشد")

#     update_data = job_posting_update.model_dump(exclude_unset=True)

#     job_posting.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(job_posting)

#     return job_posting


# @router.delete(
#     "/job_postings/{job_posting_id}",
#     response_model=dict[str, str],
# )
# async def delete_job_posting(
#     *,
#     session: AsyncSession = Depends(get_session),
#     job_posting_id: UUID,
# ):
#     job_posting = await session.get(JobPosting, job_posting_id)
#     if not job_posting:
#         raise HTTPException(status_code=404, detail="آگهی شغلی پیدا نشد")

#     await session.delete(job_posting)
#     await session.commit()

#     return {"msg": "آگهی شغلی با موفقیت حذف شد"}


# @router.get(
#     "/job_postings/search/",
#     response_model=list[RelationalJobPostingPublic],
# )
# async def search_job_postings(
#         *,
#         session: AsyncSession = Depends(get_session),
#         title: str | None = None,
#         location: IranProvinces | None = None,
#         job_description: str | None = None,
#         employment_type: JobPostingEmploymentType | None = None,
#         posted_date: str | None = None,
#         expiry_date: str | None = None,
#         salary_unit: JobPostingSalaryUnit | None = None,
#         salary_range: int | None = None,
#         job_categoriy: JobPostingJobCategory | None = None,
#         vacancy_count: int | None = None,
#         status: JobPostingStatus | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if title:
#         conditions.append(JobPosting.title.ilike(f"%{title}%"))
#     if location:
#         conditions.append(JobPosting.location == location)
#     if job_description:
#         conditions.append(JobPosting.job_description.ilike(f"%{job_description}%"))
#     if employment_type:
#         conditions.append(JobPosting.employment_type == employment_type)
#     if posted_date:
#         conditions.append(JobPosting.posted_date == posted_date)
#     if expiry_date:
#         conditions.append(JobPosting.expiry_date == expiry_date)
#     if salary_unit:
#         conditions.append(JobPosting.salary_unit == salary_unit)
#     if salary_range:
#         conditions.append(JobPosting.salary_range == salary_range)
#     if job_categoriy:
#         conditions.append(JobPosting.job_categoriy == job_categoriy)
#     if vacancy_count:
#         conditions.append(JobPosting.vacancy_count == vacancy_count)
#     if status:
#         conditions.append(JobPosting.status == status)

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(JobPosting).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(JobPosting).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(JobPosting).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     job_posting = result.all()
#     if not job_posting:
#         raise HTTPException(status_code=404, detail="آگهی شغلی پیدا نشد")

#     return job_posting
