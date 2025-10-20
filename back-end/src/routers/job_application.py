from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import JobApplication
from schemas.relational_schemas import RelationalJobApplicationPublic
from sqlmodel import and_, not_, or_, select

from schemas.job_application import JobApplicationCreate, JobApplicationUpdate
from utilities.enumerables import JobApplicationStatus, LogicalOperator


router = APIRouter()


@router.get(
    "/job_applications/",
    response_model=list[RelationalJobApplicationPublic],
)
async def get_job_applications(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    job_applications_query = select(JobApplication).offset(offset).limit(limit).order_by(JobApplication.created_at)
    job_applications = await session.exec(job_applications_query)
    return job_applications.all()


@router.post(
    "/job_applications/",
    response_model=RelationalJobApplicationPublic,
)
async def create_job_application(
        *,
        session: AsyncSession = Depends(get_session),
        job_application_create: JobApplicationCreate,
):
    try:
        db_job_application = JobApplication(
            application_date=job_application_create.application_date,
            status=job_application_create.status,
            cover_letter=job_application_create.cover_letter,
            job_posting_id=job_application_create.job_posting_id,
            job_seeker_resume_id=job_application_create.job_seeker_resume_id
        )

        session.add(db_job_application)
        await session.commit()
        await session.refresh(db_job_application)

        return db_job_application

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد درخواست کار: "
        )


@router.get(
    "/job_applications/{job_application_id}",
    response_model=RelationalJobApplicationPublic,
)
async def get_job_application(
        *,
        session: AsyncSession = Depends(get_session),
        job_application_id: UUID,
):
    job_application = await session.get(JobApplication, job_application_id)
    if not job_application:
        raise HTTPException(status_code=404, detail="درخواست کار پیدا نشد")

    return job_application


@router.patch(
    "/job_applications/{job_application_id}",
    response_model=RelationalJobApplicationPublic,
)
async def patch_job_application(
        *,
        session: AsyncSession = Depends(get_session),
        job_application_id: UUID,
        job_application_update: JobApplicationUpdate,
):
    job_application = await session.get(JobApplication, job_application_id)
    if not job_application:
        raise HTTPException(status_code=404, detail="درخواست کار پیدا نشد")

    update_data = job_application_update.model_dump(exclude_unset=True)

    job_application.sqlmodel_update(update_data)

    await session.commit()
    await session.refresh(job_application)

    return job_application


@router.delete(
    "/job_applications/{job_application_id}",
    response_model=dict[str, str],
)
async def delete_job_application(
    *,
    session: AsyncSession = Depends(get_session),
    job_application_id: UUID,
):
    job_application = await session.get(JobApplication, job_application_id)
    if not job_application:
        raise HTTPException(status_code=404, detail="درخواست کار پیدا نشد")

    await session.delete(job_application)
    await session.commit()

    return {"msg": "درخواست کار با موفقیت حذف شد"}


@router.get(
    "/job_applications/search/",
    response_model=list[RelationalJobApplicationPublic],
)
async def search_job_applications(
        *,
        session: AsyncSession = Depends(get_session),
        application_date: str | None = None,
        status: JobApplicationStatus | None = None,
        cover_letter: str | None = None,
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if application_date:
        conditions.append(JobApplication.application_date == application_date)
    if status:
        conditions.append(JobApplication.status == status)
    if cover_letter:
        conditions.append(JobApplication.cover_letter.ilike(f"%{cover_letter}%"))

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(JobApplication).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(JobApplication).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(JobApplication).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    job_applications = result.all()
    if not job_applications:
        raise HTTPException(status_code=404, detail="درخواست کار پیدا نشد")

    return job_applications
