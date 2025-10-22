from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import JobSeekerResume, JobSeekerWorkExperience
from schemas.job_seeker_work_experience import JobSeekerWorkExperienceCreate, JobSeekerWorkExperienceUpdate
from schemas.relational_schemas import RelationalJobSeekerWorkExperiencePublic
from sqlmodel import and_, not_, or_, select

from utilities.enumerables import LogicalOperator, UserRole


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
    "/job_seeker_work_experiences/",
    response_model=list[RelationalJobSeekerWorkExperiencePublic],
)
async def get_job_seeker_work_experiences(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
):
    """
    List work experiences.
    - FULL_ADMIN / ADMIN: see all experiences (paginated)
    - EMPLOYER: read-only, can see all experiences
    - JOB_SEEKER: see only experiences tied to their resume(s)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        # JOB_SEEKER: restrict to their own resume(s)
        resumes_stmt = select(JobSeekerResume.id).where(JobSeekerResume.user_id == requester_id)
        resume_ids = (await session.exec(resumes_stmt)).all()
        if not resume_ids:
            return []
        stmt = (
            select(JobSeekerWorkExperience)
            .where(JobSeekerWorkExperience.job_seeker_resume_id.in_(resume_ids))
            .order_by(JobSeekerWorkExperience.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: see all
        stmt = (
            select(JobSeekerWorkExperience)
            .order_by(JobSeekerWorkExperience.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/job_seeker_work_experiences/",
    response_model=RelationalJobSeekerWorkExperiencePublic,
)
async def create_job_seeker_work_experience(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_work_experience_create: JobSeekerWorkExperienceCreate,
    _user: dict = WRITE_ROLE_DEP,
):
    """
    Create a work experience.
    - JOB_SEEKER: can create only for their own resume(s) -> job_seeker_resume_id must belong to them
    - ADMIN / FULL_ADMIN: can create for any resume_id
    - EMPLOYER: cannot create (write excluded)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    resume_id = job_seeker_work_experience_create.job_seeker_resume_id
    if requester_role == UserRole.JOB_SEEKER.value:
        if resume_id is None:
            raise HTTPException(status_code=400, detail="job_seeker_resume_id is required")
        resume = await session.get(JobSeekerResume, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        if str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="You cannot add experience to another user's resume")

    try:
        db_jswe = JobSeekerWorkExperience(
            title=job_seeker_work_experience_create.title,
            company_name=job_seeker_work_experience_create.company_name,
            start_date=job_seeker_work_experience_create.start_date,
            end_date=job_seeker_work_experience_create.end_date,
            description=job_seeker_work_experience_create.description,
            job_seeker_resume_id=resume_id,
        )

        session.add(db_jswe)
        await session.commit()
        await session.refresh(db_jswe)

        return db_jswe

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating job seeker work experience: {e}")


@router.get(
    "/job_seeker_work_experiences/{job_seeker_work_experience_id}",
    response_model=RelationalJobSeekerWorkExperiencePublic,
)
async def get_job_seeker_work_experience(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_work_experience_id: UUID,
    _user: dict = READ_ROLE_DEP,
):
    """
    Retrieve a single work experience.
    - FULL_ADMIN / ADMIN / EMPLOYER: allowed
    - JOB_SEEKER: only if this experience belongs to one of their resumes
    """
    jswe = await session.get(JobSeekerWorkExperience, job_seeker_work_experience_id)
    if not jswe:
        raise HTTPException(status_code=404, detail="Work experience not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jswe.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to access this resource")

    return jswe


@router.patch(
    "/job_seeker_work_experiences/{job_seeker_work_experience_id}",
    response_model=RelationalJobSeekerWorkExperiencePublic,
)
async def patch_job_seeker_work_experience(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_work_experience_id: UUID,
    job_seeker_work_experience_update: JobSeekerWorkExperienceUpdate,
    _user: dict = WRITE_ROLE_DEP,
):
    """
    Update a work experience.
    - FULL_ADMIN / ADMIN: can update any fields for any record
    - JOB_SEEKER: can update only their own experiences; cannot reassign to another resume
    - EMPLOYER: cannot update (write excluded)
    """
    jswe = await session.get(JobSeekerWorkExperience, job_seeker_work_experience_id)
    if not jswe:
        raise HTTPException(status_code=404, detail="Work experience not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jswe.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to modify this resource")

    update_data = job_seeker_work_experience_update.model_dump(exclude_unset=True)

    # Prevent JOB_SEEKER from changing ownership to another resume
    if requester_role == UserRole.JOB_SEEKER.value and "job_seeker_resume_id" in update_data:
        raise HTTPException(status_code=403, detail="You cannot change the resume_id of this experience")

    # If ADMIN/FULL_ADMIN changed job_seeker_resume_id, validate target resume exists
    if "job_seeker_resume_id" in update_data:
        new_resume = await session.get(JobSeekerResume, update_data["job_seeker_resume_id"])
        if not new_resume:
            raise HTTPException(status_code=404, detail="Target resume not found")

    # Apply updates
    for field, value in update_data.items():
        setattr(jswe, field, value)

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
    _user: dict = WRITE_ROLE_DEP,
):
    """
    Delete a work experience.
    - FULL_ADMIN / ADMIN: can delete any
    - JOB_SEEKER: can delete only their own experiences
    - EMPLOYER: cannot delete (write excluded)
    """
    jswe = await session.get(JobSeekerWorkExperience, job_seeker_work_experience_id)
    if not jswe:
        raise HTTPException(status_code=404, detail="Work experience not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jswe.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to delete this resource")

    await session.delete(jswe)
    await session.commit()
    return {"msg": "Work experience deleted successfully"}


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
    operator: LogicalOperator = Query(
        default=LogicalOperator.AND,
        description="Logical operator to combine filters: AND | OR | NOT",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
):
    """
    Search experiences:
    - FULL_ADMIN / ADMIN: search across all experiences
    - EMPLOYER: read-only, can search across all experiences
    - JOB_SEEKER: search within their own experiences only
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if title:
        conditions.append(JobSeekerWorkExperience.title.ilike(f"%{title}%"))
    if company_name:
        conditions.append(JobSeekerWorkExperience.company_name.ilike(f"%{company_name}%"))
    if start_date:
        conditions.append(JobSeekerWorkExperience.start_date == start_date)
    if end_date:
        conditions.append(JobSeekerWorkExperience.end_date == end_date)
    if job_seeker_resume_id:
        conditions.append(JobSeekerWorkExperience.job_seeker_resume_id == job_seeker_resume_id)

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
        final_where = and_(where_clause, JobSeekerWorkExperience.job_seeker_resume_id.in_(resume_ids))
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: no extra restriction
        final_where = where_clause

    stmt = (
        select(JobSeekerWorkExperience)
        .where(final_where)
        .order_by(JobSeekerWorkExperience.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()