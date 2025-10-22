from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import JobSeekerResume, User
from schemas.relational_schemas import RelationalJobSeekerResumePublic
from sqlmodel import and_, not_, or_, select

from schemas.job_seeker_resume import JobSeekerResumeCreate, JobSeekerResumeUpdate
from utilities.authentication import get_password_hash
from utilities.enumerables import EmploymentStatusJobSeekerResume, LogicalOperator, UserRole
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
    "/job_seeker_resumes/",
    response_model=list[RelationalJobSeekerResumePublic],
)
async def get_job_seeker_resumes(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    List job seeker resumes.
    - FULL_ADMIN / ADMIN: see all resumes (paginated)
    - EMPLOYER: read-only, can see all resumes
    - JOB_SEEKER: see only their own resumes
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        # JOB_SEEKER: only their own resumes
        stmt = (
            select(JobSeekerResume)
            .where(JobSeekerResume.user_id == requester_id)
            .order_by(JobSeekerResume.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: see all
        stmt = (
            select(JobSeekerResume)
            .order_by(JobSeekerResume.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/job_seeker_resumes/",
    response_model=RelationalJobSeekerResumePublic,
)
async def create_job_seeker_resume(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_resume_create: JobSeekerResumeCreate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Create a resume.
    - JOB_SEEKER: can only create their own resume (user_id will be overridden to requester)
    - ADMIN / FULL_ADMIN: can create for any user_id provided
    - EMPLOYER: cannot create (write excluded)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    # Determine target user_id safely
    if requester_role == UserRole.JOB_SEEKER.value:
        user_id = requester_id
    else:
        # ADMIN / FULL_ADMIN: allow client-provided user_id but validate user exists
        user_id = job_seeker_resume_create.user_id
        if user_id is None:
            raise HTTPException(status_code=400, detail="user_id is required for admins")
        target_user = await session.get(User, user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")

    try:
        db_jsr = JobSeekerResume(
            job_title=job_seeker_resume_create.job_title,
            professional_summary=job_seeker_resume_create.professional_summary,
            employment_status=(
                job_seeker_resume_create.employment_status.value
                if hasattr(job_seeker_resume_create.employment_status, "value")
                else job_seeker_resume_create.employment_status
            ),
            is_visible=job_seeker_resume_create.is_visible,
            user_id=user_id,
        )

        session.add(db_jsr)
        await session.commit()
        await session.refresh(db_jsr)

        return db_jsr

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating job seeker resume: {e}")


@router.get(
    "/job_seeker_resumes/{job_seeker_resume_id}",
    response_model=RelationalJobSeekerResumePublic,
)
async def get_job_seeker_resume(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_resume_id: UUID,
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve a single resume.
    - FULL_ADMIN / ADMIN / EMPLOYER: allowed
    - JOB_SEEKER: only their own resume
    """
    jsr = await session.get(JobSeekerResume, job_seeker_resume_id)
    if not jsr:
        raise HTTPException(status_code=404, detail="Job seeker resume not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value and str(jsr.user_id) != str(requester_id):
        raise HTTPException(status_code=403, detail="Not allowed to access this resume")

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
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Update a resume.
    - FULL_ADMIN / ADMIN: can update any resume (including user_id)
    - JOB_SEEKER: can update only their own resumes; cannot change user_id
    - EMPLOYER: cannot update (write excluded)
    """
    jsr = await session.get(JobSeekerResume, job_seeker_resume_id)
    if not jsr:
        raise HTTPException(status_code=404, detail="Job seeker resume not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value and str(jsr.user_id) != str(requester_id):
        raise HTTPException(status_code=403, detail="Not allowed to modify this resume")

    update_data = job_seeker_resume_update.model_dump(exclude_unset=True)

    # Prevent JOB_SEEKER from changing ownership
    if requester_role == UserRole.JOB_SEEKER.value and "user_id" in update_data:
        raise HTTPException(status_code=403, detail="You cannot change the user_id of your resume")

    # If ADMIN/FULL_ADMIN changed user_id, validate target user exists
    if "user_id" in update_data:
        new_user = await session.get(User, update_data["user_id"])
        if not new_user:
            raise HTTPException(status_code=404, detail="Target user not found")

    # Normalize enum value if present
    if "employment_status" in update_data and hasattr(update_data["employment_status"], "value"):
        update_data["employment_status"] = update_data["employment_status"].value

    # Apply updates
    for field, value in update_data.items():
        setattr(jsr, field, value)

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
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete a resume.
    - FULL_ADMIN / ADMIN: can delete any resume
    - JOB_SEEKER: can delete only their own resumes
    - EMPLOYER: cannot delete (write excluded)
    """
    jsr = await session.get(JobSeekerResume, job_seeker_resume_id)
    if not jsr:
        raise HTTPException(status_code=404, detail="Job seeker resume not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value and str(jsr.user_id) != str(requester_id):
        raise HTTPException(status_code=403, detail="Not allowed to delete this resume")

    await session.delete(jsr)
    await session.commit()
    return {"msg": "Job seeker resume deleted successfully"}


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
    Search resumes:
    - FULL_ADMIN / ADMIN / EMPLOYER: can search across all resumes (ADMIN/FULL_ADMIN full access)
    - JOB_SEEKER: search limited to their own resume(s) only
    - NOT interpreted as NOT(OR(...))
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if job_title:
        conditions.append(JobSeekerResume.job_title.ilike(f"%{job_title}%"))
    if professional_summary:
        conditions.append(JobSeekerResume.professional_summary.ilike(f"%{professional_summary}%"))
    if employment_status is not None:
        val = employment_status.value if hasattr(employment_status, "value") else employment_status
        conditions.append(JobSeekerResume.employment_status == val)
    if is_visible is not None:
        conditions.append(JobSeekerResume.is_visible == is_visible)
    if user_id is not None:
        conditions.append(JobSeekerResume.user_id == user_id)

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
        # Restrict to the caller's resumes regardless of provided user_id
        final_where = and_(where_clause, JobSeekerResume.user_id == requester_id)
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: no extra restriction
        final_where = where_clause

    stmt = (
        select(JobSeekerResume)
        .where(final_where)
        .order_by(JobSeekerResume.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()


# @router.get(
#     "/job_seeker_resumes/",
#     response_model=list[RelationalJobSeekerResumePublic],
# )
# async def get_job_seeker_resumes(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     jsrs_query = select(JobSeekerResume).offset(offset).limit(limit).order_by(JobSeekerResume.created_at)
#     jsrs = await session.exec(jsrs_query)
#     return jsrs.all()


# @router.post(
#     "/job_seeker_resumes/",
#     response_model=RelationalJobSeekerResumePublic,
# )
# async def create_job_seeker_resume(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_resume_create: JobSeekerResumeCreate,
# ):
#     try:
#         db_jsr = JobSeekerResume(
#             job_title=job_seeker_resume_create.job_title,
#             professional_summary=job_seeker_resume_create.professional_summary,
#             employment_status=job_seeker_resume_create.employment_status,
#             is_visible=job_seeker_resume_create.is_visible,
#             user_id=job_seeker_resume_create.user_id
#         )

#         session.add(db_jsr)
#         await session.commit()
#         await session.refresh(db_jsr)

#         return db_jsr

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد رزومه کارجو: "
#         )


# @router.get(
#     "/job_seeker_resumes/{job_seeker_resume_id}",
#     response_model=RelationalJobSeekerResumePublic,
# )
# async def get_job_seeker_resume(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_resume_id: UUID,
# ):
#     jsr = await session.get(JobSeekerResume, job_seeker_resume_id)
#     if not jsr:
#         raise HTTPException(status_code=404, detail="رزومه کارجو پیدا نشد")

#     return jsr


# @router.patch(
#     "/job_seeker_resumes/{job_seeker_resume_id}",
#     response_model=RelationalJobSeekerResumePublic,
# )
# async def patch_job_seeker_resume(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_resume_id: UUID,
#         job_seeker_resume_update: JobSeekerResumeUpdate,
# ):
#     jsr = await session.get(JobSeekerResume, job_seeker_resume_id)
#     if not jsr:
#         raise HTTPException(status_code=404, detail="رزومه کارجو پیدا نشد")

#     update_data = job_seeker_resume_update.model_dump(exclude_unset=True)
#     if "password" in update_data:
#         update_data["password"] = get_password_hash(update_data["password"])

#     jsr.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(jsr)

#     return jsr


# @router.delete(
#     "/job_seeker_resumes/{job_seeker_resume_id}",
#     response_model=dict[str, str],
# )
# async def delete_job_seeker_resume(
#     *,
#     session: AsyncSession = Depends(get_session),
#     job_seeker_resume_id: UUID,
# ):
#     jsr = await session.get(JobSeekerResume, job_seeker_resume_id)
#     if not jsr:
#         raise HTTPException(status_code=404, detail="رزومه کارجو پیدا نشد")

#     await session.delete(jsr)
#     await session.commit()

#     return {"msg": "رزومه کارجو با موفقیت حذف شد"}


# @router.get(
#     "/job_seeker_resumes/search/",
#     response_model=list[RelationalJobSeekerResumePublic],
# )
# async def search_job_seeker_resumes(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_title: str | None = None,
#         professional_summary: str | None = None,
#         employment_status: EmploymentStatusJobSeekerResume | None = None,
#         is_visible: bool | None = None,
#         user_id: UUID | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if job_title:
#         conditions.append(JobSeekerResume.job_title.ilike(f"%{job_title}%"))
#     if professional_summary:
#         conditions.append(JobSeekerResume.professional_summary == professional_summary)
#     if employment_status:
#         conditions.append(JobSeekerResume.employment_status == employment_status)
#     if is_visible:
#         conditions.append(JobSeekerResume.is_visible == is_visible)
#     if user_id:
#         conditions.append(JobSeekerResume.user_id == user_id)

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(JobSeekerResume).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(JobSeekerResume).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(JobSeekerResume).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     jsrs = result.all()
#     if not jsrs:
#         raise HTTPException(status_code=404, detail="رزومه کارجو پیدا نشد")

#     return jsrs
