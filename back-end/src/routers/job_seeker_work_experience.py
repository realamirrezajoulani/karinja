from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import JobSeekerWorkExperience
from schemas.job_seeker_work_experience import JobSeekerWorkExperienceCreate, JobSeekerWorkExperienceUpdate
from schemas.relational_schemas import RelationalJobSeekerWorkExperiencePublic
from sqlmodel import and_, not_, or_, select

from utilities.enumerables import LogicalOperator


router = APIRouter()


@router.get(
    "/job_seeker_work_experiences/",
    response_model=list[RelationalJobSeekerWorkExperiencePublic],
)
async def get_job_seeker_work_experiences(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    jswe_query = select(JobSeekerWorkExperience).offset(offset).limit(limit).order_by(JobSeekerWorkExperience.created_at)
    jswe = await session.exec(jswe_query)
    return jswe.all()


@router.post(
    "/job_seeker_work_experiences/",
    response_model=RelationalJobSeekerWorkExperiencePublic,
)
async def create_job_seeker_work_experience(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_work_experience_create: JobSeekerWorkExperienceCreate,
):
    try:
        db_jswe = JobSeekerWorkExperience(
            title=job_seeker_work_experience_create.title,
            company_name=job_seeker_work_experience_create.company_name,
            start_date=job_seeker_work_experience_create.start_date,
            end_date=job_seeker_work_experience_create.end_date,
            description=job_seeker_work_experience_create.description,
            job_seeker_resume_id=job_seeker_work_experience_create.job_seeker_resume_id
        )

        session.add(db_jswe)
        await session.commit()
        await session.refresh(db_jswe)

        return db_jswe

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد تجربه کاری کارجو: "
        )


@router.get(
    "/job_seeker_work_experiences/{job_seeker_work_experience_id}",
    response_model=RelationalJobSeekerWorkExperiencePublic,
)
async def get_job_seeker_work_experience(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_work_experience_id: UUID,
):
    jss = await session.get(JobSeekerWorkExperience, job_seeker_work_experience_id)
    if not jss:
        raise HTTPException(status_code=404, detail="تجربه کاری کارجو پیدا نشد")

    return jss


@router.patch(
    "/job_seeker_work_experiences/{job_seeker_work_experience_id}",
    response_model=RelationalJobSeekerWorkExperiencePublic,
)
async def patch_job_seeker_work_experience(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_work_experience_id: UUID,
        job_seeker_work_experience_update: JobSeekerWorkExperienceUpdate,
):
    jswe = await session.get(JobSeekerWorkExperience, job_seeker_work_experience_id)
    if not jswe:
        raise HTTPException(status_code=404, detail="تجربه کاری کارجو پیدا نشد")

    update_data = job_seeker_work_experience_update.model_dump(exclude_unset=True)
    jswe.sqlmodel_update(update_data)

    await session.commit()
    await session.refresh(jswe)

    return jswe


@router.delete(
    "/job_seeker_work_experiences/{job_seeker_work_experience_id}",
    response_model=dict[str, str],
)
async def delete_job_seeker_work_experience(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_work_experience_id: UUID,
):
    jswe = await session.get(JobSeekerWorkExperience, job_seeker_work_experience_id)
    if not jswe:
        raise HTTPException(status_code=404, detail="تجربه کاری کارجو پیدا نشد")

    await session.delete(jswe)
    await session.commit()

    return {"msg": "تجربه کاری کارجو با موفقیت حذف شد"}


@router.get(
    "/job_seeker_work_experiences/search/",
    response_model=list[RelationalJobSeekerWorkExperiencePublic],
)
async def search_job_seeker_work_experiences(
        *,
        session: AsyncSession = Depends(get_session),
        title: str | None = None,
        company_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        job_seeker_resume_id: UUID | None = None,
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if title:
        conditions.append(JobSeekerWorkExperience.title.ilike(f"%{title}%"))
    if company_name:
        conditions.append(JobSeekerWorkExperience.company_name.ilike(f"%{title}%"))
    if start_date:
        conditions.append(JobSeekerWorkExperience.start_date == start_date)
    if end_date:
        conditions.append(JobSeekerWorkExperience.end_date == end_date)
    if job_seeker_resume_id:
        conditions.append(JobSeekerWorkExperience.job_seeker_resume_id == job_seeker_resume_id)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(JobSeekerWorkExperience).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(JobSeekerWorkExperience).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(JobSeekerWorkExperience).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    jswe = result.all()
    if not jswe:
        raise HTTPException(status_code=404, detail="تجربه کاری کارجو پیدا نشد")

    return jswe
