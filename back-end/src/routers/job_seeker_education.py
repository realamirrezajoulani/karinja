from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import JobSeekerEducation
from schemas.job_seeker_education import JobSeekerEducationCreate, JobSeekerEducationUpdate
from schemas.relational_schemas import RelationalJobSeekerEducationPublic
from sqlmodel import and_, not_, or_, select

from utilities.enumerables import JobSeekerEducationDegree, LogicalOperator


router = APIRouter()


@router.get(
    "/job_seeker_educations/",
    response_model=list[RelationalJobSeekerEducationPublic],
)
async def get_job_seeker_educations(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    jse_query = select(JobSeekerEducation).offset(offset).limit(limit).order_by(JobSeekerEducation.created_at)
    jse = await session.exec(jse_query)
    return jse.all()


@router.post(
    "/job_seeker_educations/",
    response_model=RelationalJobSeekerEducationPublic,
)
async def create_job_seeker_education(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_education_create: JobSeekerEducationCreate,
):
    try:
        db_jse = JobSeekerEducation(
            institution_name=job_seeker_education_create.institution_name,
            degree=job_seeker_education_create.degree,
            study_field=job_seeker_education_create.study_field,
            start_date=job_seeker_education_create.start_date,
            end_date=job_seeker_education_create.end_date,
            description=job_seeker_education_create.description,
            job_seeker_resume_id=job_seeker_education_create.job_seeker_resume_id
        )

        session.add(db_jse)
        await session.commit()
        await session.refresh(db_jse)

        return db_jse

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد تحصیلات کارجو: "
        )


@router.get(
    "/job_seeker_educations/{job_seeker_education_id}",
    response_model=RelationalJobSeekerEducationPublic,
)
async def get_job_seeker_education(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_education_id: UUID,
):
    jse = await session.get(JobSeekerEducation, job_seeker_education_id)
    if not jse:
        raise HTTPException(status_code=404, detail="تحصیلات کارجو پیدا نشد")

    return jse


@router.patch(
    "/job_seeker_educations/{job_seeker_education_id}",
    response_model=RelationalJobSeekerEducationPublic,
)
async def patch_job_seeker_education(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_education_id: UUID,
        job_seeker_education_update: JobSeekerEducationUpdate,
):
    jse = await session.get(JobSeekerEducation, job_seeker_education_id)
    if not jse:
        raise HTTPException(status_code=404, detail="تحصیلات کارجو پیدا نشد")

    update_data = job_seeker_education_update.model_dump(exclude_unset=True)
    jse.sqlmodel_update(update_data)

    await session.commit()
    await session.refresh(jse)

    return jse


@router.delete(
    "/job_seeker_educations/{job_seeker_education_id}",
    response_model=dict[str, str],
)
async def delete_job_seeker_education(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_education_id: UUID
):
    jse = await session.get(JobSeekerEducation, job_seeker_education_id)
    if not jse:
        raise HTTPException(status_code=404, detail="تحصیلات کارجو پیدا نشد")

    await session.delete(jse)
    await session.commit()

    return {"msg": "تحصیلات کارجو با موفقیت حذف شد"}


@router.get(
    "/job_seeker_educations/search/",
    response_model=list[RelationalJobSeekerEducationPublic],
)
async def search_job_seeker_educations(
        *,
        session: AsyncSession = Depends(get_session),
        institution_name: str | None = None,
        degree: JobSeekerEducationDegree | None = None,
        study_field: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        job_seeker_resume_id: UUID | None = None,
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if institution_name:
        conditions.append(JobSeekerEducation.institution_name.ilike(f"%{institution_name}%"))
    if degree:
        conditions.append(JobSeekerEducation.degree == degree)
    if study_field:
        conditions.append(JobSeekerEducation.study_field.ilike(f"%{study_field}%"))
    if start_date:
        conditions.append(JobSeekerEducation.start_date == start_date)
    if end_date:
        conditions.append(JobSeekerEducation.end_date == end_date)
    if job_seeker_resume_id:
        conditions.append(JobSeekerEducation.job_seeker_resume_id == job_seeker_resume_id)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(JobSeekerEducation).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(JobSeekerEducation).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(JobSeekerEducation).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    jse = result.all()
    if not jse:
        raise HTTPException(status_code=404, detail="تحصیلات کارجو پیدا نشد")

    return jse
