from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import JobSeekerResume, JobSeekerSkill
from schemas.job_seeker_skill import JobSeekerSkillCreate, JobSeekerSkillUpdate
from schemas.relational_schemas import RelationalJobSeekerSkillPublic
from sqlmodel import and_, not_, or_, select

from utilities.enumerables import JobSeekerCertificateVerificationStatus, JobSeekerProficiencyLevel, LogicalOperator, UserRole
from utilities.authentication import oauth2_scheme


router = APIRouter()


# Roles allowed to READ (includes Employer for read-only)
READ_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.JOB_SEEKER.value,
        UserRole.EMPLOYER.value,
    )
)

# Roles allowed to WRITE (Employer excluded)
WRITE_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.JOB_SEEKER.value,
    )
)


@router.get(
    "/job_seeker_skills/",
    response_model=list[RelationalJobSeekerSkillPublic],
)
async def get_job_seeker_skills(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    List skills.
    - FULL_ADMIN / ADMIN: see all skills
    - EMPLOYER: read-only, can see all skills
    - JOB_SEEKER: see only skills tied to their resume(s)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        # Restrict to the requester's resume(s)
        resumes_stmt = select(JobSeekerResume.id).where(JobSeekerResume.user_id == requester_id)
        resume_ids = (await session.exec(resumes_stmt)).all()
        if not resume_ids:
            return []
        stmt = (
            select(JobSeekerSkill)
            .where(JobSeekerSkill.job_seeker_resume_id.in_(resume_ids))
            .order_by(JobSeekerSkill.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: see all
        stmt = (
            select(JobSeekerSkill)
            .order_by(JobSeekerSkill.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/job_seeker_skills/",
    response_model=RelationalJobSeekerSkillPublic,
)
async def create_job_seeker_skill(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_skill_create: JobSeekerSkillCreate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Create a skill.
    - JOB_SEEKER: can create only for their own resume(s) -> job_seeker_resume_id must belong to them
    - ADMIN / FULL_ADMIN: can create for any resume_id
    - EMPLOYER: cannot create (write excluded)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    resume_id = job_seeker_skill_create.job_seeker_resume_id
    if requester_role == UserRole.JOB_SEEKER.value:
        if resume_id is None:
            raise HTTPException(status_code=400, detail="job_seeker_resume_id is required")
        resume = await session.get(JobSeekerResume, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        if str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="You cannot add a skill to another user's resume")

    try:
        db_jss = JobSeekerSkill(
            title=job_seeker_skill_create.title,
            proficiency_level=(
                job_seeker_skill_create.proficiency_level.value
                if hasattr(job_seeker_skill_create.proficiency_level, "value")
                else job_seeker_skill_create.proficiency_level
            ),
            has_certificate=job_seeker_skill_create.has_certificate,
            certificate_issuing_organization=job_seeker_skill_create.certificate_issuing_organization,
            certificate_code=job_seeker_skill_create.certificate_code,
            certificate_verification_status=(
                job_seeker_skill_create.certificate_verification_status.value
                if hasattr(job_seeker_skill_create.certificate_verification_status, "value")
                else job_seeker_skill_create.certificate_verification_status
            ),
            job_seeker_resume_id=resume_id,
        )

        session.add(db_jss)
        await session.commit()
        await session.refresh(db_jss)

        return db_jss

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating job seeker skill: {e}")


@router.get(
    "/job_seeker_skills/{job_seeker_skill_id}",
    response_model=RelationalJobSeekerSkillPublic,
)
async def get_job_seeker_skill(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_skill_id: UUID,
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve a single skill.
    - FULL_ADMIN / ADMIN / EMPLOYER: allowed
    - JOB_SEEKER: only if this skill belongs to one of their resumes
    """
    jss = await session.get(JobSeekerSkill, job_seeker_skill_id)
    if not jss:
        raise HTTPException(status_code=404, detail="Job seeker skill not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jss.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to access this resource")

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
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Update a skill.
    - FULL_ADMIN / ADMIN: can update any fields for any record
    - JOB_SEEKER: can update only their own skills; cannot reassign to another resume
    - EMPLOYER: cannot update (write excluded)
    """
    jss = await session.get(JobSeekerSkill, job_seeker_skill_id)
    if not jss:
        raise HTTPException(status_code=404, detail="Job seeker skill not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jss.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to modify this resource")

    update_data = job_seeker_skill_update.model_dump(exclude_unset=True)

    # Prevent JOB_SEEKER from changing ownership to another resume
    if requester_role == UserRole.JOB_SEEKER.value and "job_seeker_resume_id" in update_data:
        raise HTTPException(status_code=403, detail="You cannot change the resume_id of this skill")

    # If ADMIN/FULL_ADMIN changed job_seeker_resume_id, validate target resume exists
    if "job_seeker_resume_id" in update_data:
        new_resume = await session.get(JobSeekerResume, update_data["job_seeker_resume_id"])
        if not new_resume:
            raise HTTPException(status_code=404, detail="Target resume not found")

    # Normalize enums if provided
    if "proficiency_level" in update_data and hasattr(update_data["proficiency_level"], "value"):
        update_data["proficiency_level"] = update_data["proficiency_level"].value
    if "certificate_verification_status" in update_data and hasattr(update_data["certificate_verification_status"], "value"):
        update_data["certificate_verification_status"] = update_data["certificate_verification_status"].value

    # Apply updates safely
    for field, value in update_data.items():
        setattr(jss, field, value)

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
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete a skill.
    - FULL_ADMIN / ADMIN: can delete any
    - JOB_SEEKER: can delete only their own skills
    - EMPLOYER: cannot delete (write excluded)
    """
    jss = await session.get(JobSeekerSkill, job_seeker_skill_id)
    if not jss:
        raise HTTPException(status_code=404, detail="Job seeker skill not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jss.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to delete this resource")

    await session.delete(jss)
    await session.commit()
    return {"msg": "Job seeker skill deleted successfully"}


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
    Search skills:
    - FULL_ADMIN / ADMIN: search across all skills
    - EMPLOYER: read-only, can search across all skills
    - JOB_SEEKER: search within their own skills only
    - NOT interpreted as NOT(OR(...))
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if title:
        conditions.append(JobSeekerSkill.title.ilike(f"%{title}%"))
    if proficiency_level is not None:
        lvl = proficiency_level.value if hasattr(proficiency_level, "value") else proficiency_level
        conditions.append(JobSeekerSkill.proficiency_level == lvl)
    if has_certificate is not None:
        conditions.append(JobSeekerSkill.has_certificate == has_certificate)
    if certificate_issuing_organization:
        conditions.append(JobSeekerSkill.certificate_issuing_organization.ilike(f"%{certificate_issuing_organization}%"))
    if certificate_code:
        conditions.append(JobSeekerSkill.certificate_code == certificate_code)
    if certificate_verification_status is not None:
        cvs = certificate_verification_status.value if hasattr(certificate_verification_status, "value") else certificate_verification_status
        conditions.append(JobSeekerSkill.certificate_verification_status == cvs)
    if job_seeker_resume_id is not None:
        conditions.append(JobSeekerSkill.job_seeker_resume_id == job_seeker_resume_id)

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

    # Apply role-based visibility
    if requester_role == UserRole.JOB_SEEKER.value:
        resumes_stmt = select(JobSeekerResume.id).where(JobSeekerResume.user_id == requester_id)
        resume_ids = (await session.exec(resumes_stmt)).all()
        if not resume_ids:
            return []
        final_where = and_(where_clause, JobSeekerSkill.job_seeker_resume_id.in_(resume_ids))
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: no extra restriction
        final_where = where_clause

    stmt = (
        select(JobSeekerSkill)
        .where(final_where)
        .order_by(JobSeekerSkill.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()

# @router.get(
#     "/job_seeker_skills/",
#     response_model=list[RelationalJobSeekerSkillPublic],
# )
# async def get_job_seeker_skills(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     jss_query = select(JobSeekerSkill).offset(offset).limit(limit).order_by(JobSeekerSkill.created_at)
#     jss = await session.exec(jss_query)
#     return jss.all()


# @router.post(
#     "/job_seeker_skills/",
#     response_model=RelationalJobSeekerSkillPublic,
# )
# async def create_job_seeker_skill(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_skill_create: JobSeekerSkillCreate,
# ):
#     try:
#         db_jss = JobSeekerSkill(
#             title=job_seeker_skill_create.title,
#             proficiency_level=job_seeker_skill_create.proficiency_level,
#             has_certificate=job_seeker_skill_create.has_certificate,
#             certificate_issuing_organization=job_seeker_skill_create.certificate_issuing_organization,
#             certificate_code=job_seeker_skill_create.certificate_code,
#             certificate_verification_status=job_seeker_skill_create.certificate_verification_status,
#             job_seeker_resume_id=job_seeker_skill_create.job_seeker_resume_id
#         )

#         session.add(db_jss)
#         await session.commit()
#         await session.refresh(db_jss)

#         return db_jss

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد مهارت کارجو: "
#         )


# @router.get(
#     "/job_seeker_skills/{job_seeker_skill_id}",
#     response_model=RelationalJobSeekerSkillPublic,
# )
# async def get_job_seeker_skill(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_skill_id: UUID,
# ):
#     jss = await session.get(JobSeekerSkill, job_seeker_skill_id)
#     if not jss:
#         raise HTTPException(status_code=404, detail="مهارت کارجو پیدا نشد")

#     return jss


# @router.patch(
#     "/job_seeker_skills/{job_seeker_skill_id}",
#     response_model=RelationalJobSeekerSkillPublic,
# )
# async def patch_job_seeker_skill(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_skill_id: UUID,
#         job_seeker_skill_update: JobSeekerSkillUpdate,
# ):
#     jss = await session.get(JobSeekerSkill, job_seeker_skill_id)
#     if not jss:
#         raise HTTPException(status_code=404, detail="مهارت کارجو پیدا نشد")

#     update_data = job_seeker_skill_update.model_dump(exclude_unset=True)
#     jss.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(jss)

#     return jss


# @router.delete(
#     "/job_seeker_skills/{job_seeker_skill_id}",
#     response_model=dict[str, str],
# )
# async def delete_job_seeker_skill(
#     *,
#     session: AsyncSession = Depends(get_session),
#     job_seeker_skill_id: UUID,
# ):
#     jss = await session.get(JobSeekerSkill, job_seeker_skill_id)
#     if not jss:
#         raise HTTPException(status_code=404, detail="مهارت کارجو پیدا نشد")

#     await session.delete(jss)
#     await session.commit()

#     return {"msg": "مهارت کارجو با موفقیت حذف شد"}


# @router.get(
#     "/job_seeker_skills/search/",
#     response_model=list[RelationalJobSeekerSkillPublic],
# )
# async def search_job_seeker_skills(
#         *,
#         session: AsyncSession = Depends(get_session),
#         title: str | None = None,
#         proficiency_level: JobSeekerProficiencyLevel | None = None,
#         has_certificate: bool | None = None,
#         certificate_issuing_organization: str | None = None,
#         certificate_code: str | None = None,
#         certificate_verification_status: JobSeekerCertificateVerificationStatus | None = None,
#         job_seeker_resume_id: UUID | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if title:
#         conditions.append(JobSeekerSkill.title.ilike(f"%{title}%"))
#     if proficiency_level:
#         conditions.append(JobSeekerSkill.proficiency_level == proficiency_level)
#     if has_certificate:
#         conditions.append(JobSeekerSkill.has_certificate == has_certificate)
#     if certificate_issuing_organization:
#         conditions.append(JobSeekerSkill.certificate_issuing_organization == certificate_issuing_organization)
#     if certificate_code:
#         conditions.append(JobSeekerSkill.certificate_code == certificate_code)
#     if certificate_verification_status:
#         conditions.append(JobSeekerSkill.certificate_verification_status == certificate_verification_status)
#     if job_seeker_resume_id:
#         conditions.append(JobSeekerSkill.job_seeker_resume_id == job_seeker_resume_id)

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(JobSeekerSkill).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(JobSeekerSkill).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(JobSeekerSkill).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     jss = result.all()
#     if not jss:
#         raise HTTPException(status_code=404, detail="مهارت کارجو پیدا نشد")

#     return jss
