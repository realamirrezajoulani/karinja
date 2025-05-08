from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import JobSeekerResume
from schemas.relational_schemas import RelationalJobSeekerResumePublic
from sqlmodel import and_, not_, or_, select

from schemas.job_seeker_resume import JobSeekerResumeCreate, JobSeekerResumeUpdate
from utilities.authentication import get_password_hash
from utilities.enumerables import EmploymentStatusJobSeekerResume, LogicalOperator


router = APIRouter()


@router.get(
    "/job_seeker_resumes/",
    response_model=list[RelationalJobSeekerResumePublic],
)
async def get_job_seeker_resumes(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    jsrs_query = select(JobSeekerResume).offset(offset).limit(limit).order_by(JobSeekerResume.created_at)
    jsrs = await session.exec(jsrs_query)
    return jsrs.all()


@router.post(
    "/job_seeker_resumes/",
    response_model=RelationalJobSeekerResumePublic,
)
async def create_job_seeker_resume(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_resume_create: JobSeekerResumeCreate,
):
    try:
        db_jsr = JobSeekerResume(
            job_title=job_seeker_resume_create.job_title,
            professional_summary=job_seeker_resume_create.professional_summary,
            employment_status=job_seeker_resume_create.employment_status,
            is_visible=job_seeker_resume_create.is_visible,
            user_id=job_seeker_resume_create.user_id
        )

        session.add(db_jsr)
        await session.commit()
        await session.refresh(db_jsr)

        return db_jsr

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد رزومه کارجو: "
        )


@router.get(
    "/job_seeker_resumes/{job_seeker_resume_id}",
    response_model=RelationalJobSeekerResumePublic,
)
async def get_job_seeker_resume(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_resume_id: UUID,
):
    jsr = await session.get(JobSeekerResume, job_seeker_resume_id)
    if not jsr:
        raise HTTPException(status_code=404, detail="رزومه کارجو پیدا نشد")

    return jsr


@router.patch(
    "/job_seeker_resumes/{job_seeker_resume_id}",
    response_model=RelationalJobSeekerResumePublic,
)
async def patch_job_seeker_resume(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_resume_id: UUID,
        job_seeker_resume_update: JobSeekerResumeUpdate,
):
    jsr = await session.get(JobSeekerResume, job_seeker_resume_id)
    if not jsr:
        raise HTTPException(status_code=404, detail="رزومه کارجو پیدا نشد")

    update_data = job_seeker_resume_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password"] = get_password_hash(update_data["password"])

    jsr.sqlmodel_update(update_data)

    await session.commit()
    await session.refresh(jsr)

    return jsr


@router.delete(
    "/job_seeker_resumes/{job_seeker_resume_id}",
    response_model=dict[str, str],
)
async def delete_job_seeker_resume(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_resume_id: UUID,
):
    jsr = await session.get(JobSeekerResume, job_seeker_resume_id)
    if not jsr:
        raise HTTPException(status_code=404, detail="رزومه کارجو پیدا نشد")

    await session.delete(jsr)
    await session.commit()

    return {"msg": "رزومه کارجو با موفقیت حذف شد"}


@router.get(
    "/job_seeker_resumes/search/",
    response_model=list[RelationalJobSeekerResumePublic],
)
async def search_job_seeker_resumes(
        *,
        session: AsyncSession = Depends(get_session),
        job_title: str | None = None,
        professional_summary: str | None = None,
        employment_status: EmploymentStatusJobSeekerResume | None = None,
        is_visible: bool | None = None,
        user_id: UUID | None = None,
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if job_title:
        conditions.append(JobSeekerResume.job_title.ilike(f"%{job_title}%"))
    if professional_summary:
        conditions.append(JobSeekerResume.professional_summary == professional_summary)
    if employment_status:
        conditions.append(JobSeekerResume.employment_status == employment_status)
    if is_visible:
        conditions.append(JobSeekerResume.is_visible == is_visible)
    if user_id:
        conditions.append(JobSeekerResume.user_id == user_id)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(JobSeekerResume).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(JobSeekerResume).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(JobSeekerResume).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    jsrs = result.all()
    if not jsrs:
        raise HTTPException(status_code=404, detail="رزومه کارجو پیدا نشد")

    return jsrs
