from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import EmailStr

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import JobPosting
from schemas.relational_schemas import RelationalJobPostingPublic
from sqlmodel import and_, not_, or_, select

from schemas.job_posting import JobPostingCreate, JobPostingUpdate
from utilities.authentication import get_password_hash
from utilities.enumerables import IranProvinces, JobPostingEmploymentType, JobPostingJobCategory, JobPostingSalaryUnit, JobPostingStatus, LogicalOperator, UserAccountStatus, UserRole


router = APIRouter()


@router.get(
    "/job_postings/",
    response_model=list[RelationalJobPostingPublic],
)
async def get_job_postings(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    job_postings_query = select(JobPosting).offset(offset).limit(limit).order_by(JobPosting.created_at)
    job_postings = await session.exec(job_postings_query)
    return job_postings.all()


@router.post(
    "/job_postings/",
    response_model=RelationalJobPostingPublic,
)
async def create_job_posting(
        *,
        session: AsyncSession = Depends(get_session),
        job_posting_create: JobPostingCreate,
):
    try:
        db_job_posting = JobPosting(
            title=job_posting_create.title,
            location=job_posting_create.location,
            job_description=job_posting_create.job_description,
            employment_type=job_posting_create.employment_type,
            posted_date=job_posting_create.posted_date,
            expiry_date=job_posting_create.expiry_date,
            salary_unit=job_posting_create.salary_unit,
            salary_range=job_posting_create.salary_range,
            job_categoriy=job_posting_create.job_categoriy,
            vacancy_count=job_posting_create.vacancy_count,
            status=job_posting_create.status,
            company_id=job_posting_create.company_id
        )

        session.add(db_job_posting)
        await session.commit()
        await session.refresh(db_job_posting)

        return db_job_posting

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد آگهی شغلی: "
        )


@router.get(
    "/job_postings/{job_posting_id}",
    response_model=RelationalJobPostingPublic,
)
async def get_job_posting(
        *,
        session: AsyncSession = Depends(get_session),
        job_posting_id: UUID,
):
    job_posting = await session.get(JobPosting, job_posting_id)
    if not job_posting:
        raise HTTPException(status_code=404, detail="آگهی شغلی پیدا نشد")

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
):
    job_posting = await session.get(JobPosting, job_posting_id)
    if not job_posting:
        raise HTTPException(status_code=404, detail="آگهی شغلی پیدا نشد")

    update_data = job_posting_update.model_dump(exclude_unset=True)

    job_posting.sqlmodel_update(update_data)

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
):
    job_posting = await session.get(JobPosting, job_posting_id)
    if not job_posting:
        raise HTTPException(status_code=404, detail="آگهی شغلی پیدا نشد")

    await session.delete(job_posting)
    await session.commit()

    return {"msg": "آگهی شغلی با موفقیت حذف شد"}


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
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if title:
        conditions.append(JobPosting.title.ilike(f"%{title}%"))
    if location:
        conditions.append(JobPosting.location == location)
    if job_description:
        conditions.append(JobPosting.job_description.ilike(f"%{job_description}%"))
    if employment_type:
        conditions.append(JobPosting.employment_type == employment_type)
    if posted_date:
        conditions.append(JobPosting.posted_date == posted_date)
    if expiry_date:
        conditions.append(JobPosting.expiry_date == expiry_date)
    if salary_unit:
        conditions.append(JobPosting.salary_unit == salary_unit)
    if salary_range:
        conditions.append(JobPosting.salary_range == salary_range)
    if job_categoriy:
        conditions.append(JobPosting.job_categoriy == job_categoriy)
    if vacancy_count:
        conditions.append(JobPosting.vacancy_count == vacancy_count)
    if status:
        conditions.append(JobPosting.status == status)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(JobPosting).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(JobPosting).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(JobPosting).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    job_posting = result.all()
    if not job_posting:
        raise HTTPException(status_code=404, detail="آگهی شغلی پیدا نشد")

    return job_posting
