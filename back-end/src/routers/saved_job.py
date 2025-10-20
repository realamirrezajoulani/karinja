from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import SavedJob
from schemas.relational_schemas import RelationalSavedJobPublic
from sqlmodel import and_, not_, or_, select

from schemas.saved_job import SavedJobCreate, SavedJobUpdate
from utilities.enumerables import LogicalOperator


router = APIRouter()


@router.get(
    "/saved_jobs/",
    response_model=list[RelationalSavedJobPublic],
)
async def get_saved_jobs(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    saved_jobs_query = select(SavedJob).offset(offset).limit(limit).order_by(SavedJob.created_at)
    saved_jobs = await session.exec(saved_jobs_query)
    return saved_jobs.all()


@router.post(
    "/saved_jobs/",
    response_model=RelationalSavedJobPublic,
)
async def create_saved_job(
        *,
        session: AsyncSession = Depends(get_session),
        saved_job_create: SavedJobCreate,
):
    try:
        db_saved_job = SavedJob(
            saved_date=saved_job_create.saved_date,
            user_id=saved_job_create.user_id,
            job_posting_id=saved_job_create.job_posting_id,
        )

        session.add(db_saved_job)
        await session.commit()
        await session.refresh(db_saved_job)

        return db_saved_job

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد آگهی شغلی ذخیره شده: "
        )


@router.get(
    "/saved_jobs/{saved_job_id}",
    response_model=RelationalSavedJobPublic,
)
async def get_saved_job(
        *,
        session: AsyncSession = Depends(get_session),
        saved_job_id: UUID,
):
    saved_job = await session.get(SavedJob, saved_job_id)
    if not saved_job:
        raise HTTPException(status_code=404, detail="آگهی شغل ذخیره شده پیدا نشد")

    return saved_job


@router.patch(
    "/saved_jobs/{saved_job_id}",
    response_model=RelationalSavedJobPublic,
)
async def patch_saved_job(
        *,
        session: AsyncSession = Depends(get_session),
        saved_job_id: UUID,
        saved_job_update: SavedJobUpdate,
):
    saved_job = await session.get(SavedJob, saved_job_id)
    if not saved_job:
        raise HTTPException(status_code=404, detail="آگهی شغلی ذخیره شده پیدا نشد")

    update_data = saved_job_update.model_dump(exclude_unset=True)

    saved_job.sqlmodel_update(update_data)

    await session.commit()
    await session.refresh(saved_job)

    return saved_job


@router.delete(
    "/saved_jobs/{saved_job_id}",
    response_model=dict[str, str],
)
async def delete_saved_job(
    *,
    session: AsyncSession = Depends(get_session),
    saved_job_id: UUID,
):
    saved_job = await session.get(SavedJob, saved_job_id)
    if not saved_job:
        raise HTTPException(status_code=404, detail="آگهی شغلی ذخیره شده پیدا نشد")

    await session.delete(saved_job)
    await session.commit()

    return {"msg": "آگهی شغلی ذخیره شده با موفقیت حذف شد"}


@router.get(
    "/saved_jobs/search/",
    response_model=list[RelationalSavedJobPublic],
)
async def search_saved_jobs(
        *,
        session: AsyncSession = Depends(get_session),
        saved_date: str | None = None,
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if saved_date:
        conditions.append(SavedJob.saved_date == saved_date)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(SavedJob).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(SavedJob).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(SavedJob).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    saved_jobs = result.all()
    if not saved_jobs:
        raise HTTPException(status_code=404, detail="آگهی شغلی ذخیره شده پیدا نشد")

    return saved_jobs
