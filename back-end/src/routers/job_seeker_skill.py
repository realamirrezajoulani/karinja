from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import JobSeekerSkill
from schemas.job_seeker_skill import JobSeekerSkillCreate, JobSeekerSkillUpdate
from schemas.relational_schemas import RelationalJobSeekerSkillPublic
from sqlmodel import and_, not_, or_, select

from utilities.enumerables import JobSeekerCertificateVerificationStatus, JobSeekerProficiencyLevel, LogicalOperator


router = APIRouter()


@router.get(
    "/job_seeker_skills/",
    response_model=list[RelationalJobSeekerSkillPublic],
)
async def get_job_seeker_skills(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    jss_query = select(JobSeekerSkill).offset(offset).limit(limit).order_by(JobSeekerSkill.created_at)
    jss = await session.exec(jss_query)
    return jss.all()


@router.post(
    "/job_seeker_skills/",
    response_model=RelationalJobSeekerSkillPublic,
)
async def create_job_seeker_skill(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_skill_create: JobSeekerSkillCreate,
):
    try:
        db_jss = JobSeekerSkill(
            title=job_seeker_skill_create.title,
            proficiency_level=job_seeker_skill_create.proficiency_level,
            has_certificate=job_seeker_skill_create.has_certificate,
            certificate_issuing_organization=job_seeker_skill_create.certificate_issuing_organization,
            certificate_code=job_seeker_skill_create.certificate_code,
            certificate_verification_status=job_seeker_skill_create.certificate_verification_status,
            job_seeker_resume_id=job_seeker_skill_create.job_seeker_resume_id
        )

        session.add(db_jss)
        await session.commit()
        await session.refresh(db_jss)

        return db_jss

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد مهارت کارجو: "
        )


@router.get(
    "/job_seeker_skills/{job_seeker_skill_id}",
    response_model=RelationalJobSeekerSkillPublic,
)
async def get_job_seeker_skill(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_skill_id: UUID,
):
    jss = await session.get(JobSeekerSkill, job_seeker_skill_id)
    if not jss:
        raise HTTPException(status_code=404, detail="مهارت کارجو پیدا نشد")

    return jss


@router.patch(
    "/job_seeker_skills/{job_seeker_skill_id}",
    response_model=RelationalJobSeekerSkillPublic,
)
async def patch_job_seeker_skill(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_skill_id: UUID,
        job_seeker_skill_update: JobSeekerSkillUpdate,
):
    jss = await session.get(JobSeekerSkill, job_seeker_skill_id)
    if not jss:
        raise HTTPException(status_code=404, detail="مهارت کارجو پیدا نشد")

    update_data = job_seeker_skill_update.model_dump(exclude_unset=True)
    jss.sqlmodel_update(update_data)

    await session.commit()
    await session.refresh(jss)

    return jss


@router.delete(
    "/job_seeker_skills/{job_seeker_skill_id}",
    response_model=dict[str, str],
)
async def delete_job_seeker_skill(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_skill_id: UUID,
):
    jss = await session.get(JobSeekerSkill, job_seeker_skill_id)
    if not jss:
        raise HTTPException(status_code=404, detail="مهارت کارجو پیدا نشد")

    await session.delete(jss)
    await session.commit()

    return {"msg": "مهارت کارجو با موفقیت حذف شد"}


@router.get(
    "/job_seeker_skills/search/",
    response_model=list[RelationalJobSeekerSkillPublic],
)
async def search_job_seeker_skills(
        *,
        session: AsyncSession = Depends(get_session),
        title: str | None = None,
        proficiency_level: JobSeekerProficiencyLevel | None = None,
        has_certificate: bool | None = None,
        certificate_issuing_organization: str | None = None,
        certificate_code: str | None = None,
        certificate_verification_status: JobSeekerCertificateVerificationStatus | None = None,
        job_seeker_resume_id: UUID | None = None,
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if title:
        conditions.append(JobSeekerSkill.title.ilike(f"%{title}%"))
    if proficiency_level:
        conditions.append(JobSeekerSkill.proficiency_level == proficiency_level)
    if has_certificate:
        conditions.append(JobSeekerSkill.has_certificate == has_certificate)
    if certificate_issuing_organization:
        conditions.append(JobSeekerSkill.certificate_issuing_organization == certificate_issuing_organization)
    if certificate_code:
        conditions.append(JobSeekerSkill.certificate_code == certificate_code)
    if certificate_verification_status:
        conditions.append(JobSeekerSkill.certificate_verification_status == certificate_verification_status)
    if job_seeker_resume_id:
        conditions.append(JobSeekerSkill.job_seeker_resume_id == job_seeker_resume_id)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(JobSeekerSkill).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(JobSeekerSkill).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(JobSeekerSkill).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    jss = result.all()
    if not jss:
        raise HTTPException(status_code=404, detail="مهارت کارجو پیدا نشد")

    return jss
