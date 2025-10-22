from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import JobSeekerEducation, JobSeekerResume
from schemas.job_seeker_education import JobSeekerEducationCreate, JobSeekerEducationUpdate
from schemas.relational_schemas import RelationalJobSeekerEducationPublic
from sqlmodel import and_, not_, or_, select

from utilities.enumerables import JobSeekerEducationDegree, LogicalOperator, UserRole


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
    "/job_seeker_educations/",
    response_model=list[RelationalJobSeekerEducationPublic],
)
async def get_job_seeker_educations(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
):
    """
    List educations.
    - FULL_ADMIN / ADMIN: see all educations
    - EMPLOYER: read-only, can see all educations
    - JOB_SEEKER: see only educations tied to their resume(s)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        # Restrict to the requester's resumes
        resumes_stmt = select(JobSeekerResume.id).where(JobSeekerResume.user_id == requester_id)
        resume_ids = (await session.exec(resumes_stmt)).all()
        if not resume_ids:
            return []
        stmt = (
            select(JobSeekerEducation)
            .where(JobSeekerEducation.job_seeker_resume_id.in_(resume_ids))
            .order_by(JobSeekerEducation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: see all
        stmt = (
            select(JobSeekerEducation)
            .order_by(JobSeekerEducation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/job_seeker_educations/",
    response_model=RelationalJobSeekerEducationPublic,
)
async def create_job_seeker_education(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_education_create: JobSeekerEducationCreate,
    _user: dict = WRITE_ROLE_DEP,
):
    """
    Create education.
    - JOB_SEEKER: can create only for their own resume(s) -> job_seeker_resume_id must belong to them
    - ADMIN / FULL_ADMIN: can create for any resume_id
    - EMPLOYER: cannot create (write excluded)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    resume_id = job_seeker_education_create.job_seeker_resume_id
    if requester_role == UserRole.JOB_SEEKER.value:
        if resume_id is None:
            raise HTTPException(status_code=400, detail="job_seeker_resume_id is required")
        resume = await session.get(JobSeekerResume, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        if str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="You cannot add education to another user's resume")
    else:
        # For ADMIN/FULL_ADMIN, if a resume_id provided, ensure it exists
        if resume_id is not None:
            resume = await session.get(JobSeekerResume, resume_id)
            if not resume:
                raise HTTPException(status_code=404, detail="Target resume not found")

    # Normalize enum values if necessary
    degree_val = (
        job_seeker_education_create.degree.value
        if hasattr(job_seeker_education_create.degree, "value")
        else job_seeker_education_create.degree
    )

    try:
        db_jse = JobSeekerEducation(
            institution_name=job_seeker_education_create.institution_name,
            degree=degree_val,
            study_field=job_seeker_education_create.study_field,
            start_date=job_seeker_education_create.start_date,
            end_date=job_seeker_education_create.end_date,
            description=job_seeker_education_create.description,
            job_seeker_resume_id=resume_id,
        )

        session.add(db_jse)
        await session.commit()
        await session.refresh(db_jse)

        return db_jse

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating job seeker education: {e}")


@router.get(
    "/job_seeker_educations/{job_seeker_education_id}",
    response_model=RelationalJobSeekerEducationPublic,
)
async def get_job_seeker_education(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_education_id: UUID,
    _user: dict = READ_ROLE_DEP,
):
    """
    Retrieve a single education.
    - FULL_ADMIN / ADMIN / EMPLOYER: allowed
    - JOB_SEEKER: only if this record belongs to one of their resumes
    """
    jse = await session.get(JobSeekerEducation, job_seeker_education_id)
    if not jse:
        raise HTTPException(status_code=404, detail="Job seeker education not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jse.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to access this resource")

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
    _user: dict = WRITE_ROLE_DEP,
):
    """
    Update an education record.
    - FULL_ADMIN / ADMIN: can update any fields
    - JOB_SEEKER: can update only their own educations; cannot reassign to another resume
    - EMPLOYER: cannot update (write excluded)
    """
    jse = await session.get(JobSeekerEducation, job_seeker_education_id)
    if not jse:
        raise HTTPException(status_code=404, detail="Job seeker education not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jse.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to modify this resource")

    update_data = job_seeker_education_update.model_dump(exclude_unset=True)

    # Prevent JOB_SEEKER from changing ownership to another resume
    if requester_role == UserRole.JOB_SEEKER.value and "job_seeker_resume_id" in update_data:
        raise HTTPException(status_code=403, detail="You cannot change the resume_id of this education")

    # If ADMIN/FULL_ADMIN changed job_seeker_resume_id, validate target resume exists
    if "job_seeker_resume_id" in update_data:
        new_resume = await session.get(JobSeekerResume, update_data["job_seeker_resume_id"])
        if not new_resume:
            raise HTTPException(status_code=404, detail="Target resume not found")

    # Normalize degree enum if provided
    if "degree" in update_data and hasattr(update_data["degree"], "value"):
        update_data["degree"] = update_data["degree"].value

    # Apply updates
    for field, value in update_data.items():
        setattr(jse, field, value)

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
    job_seeker_education_id: UUID,
    _user: dict = WRITE_ROLE_DEP,
):
    """
    Delete an education record.
    - FULL_ADMIN / ADMIN: can delete any
    - JOB_SEEKER: can delete only their own educations
    - EMPLOYER: cannot delete (write excluded)
    """
    jse = await session.get(JobSeekerEducation, job_seeker_education_id)
    if not jse:
        raise HTTPException(status_code=404, detail="Job seeker education not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jse.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to delete this resource")

    await session.delete(jse)
    await session.commit()
    return {"msg": "Job seeker education deleted successfully"}


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
    operator: LogicalOperator = Query(
        default=LogicalOperator.AND,
        description="Logical operator to combine filters: AND | OR | NOT",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
):
    """
    Search educations:
    - FULL_ADMIN / ADMIN / EMPLOYER: can search across all educations
    - JOB_SEEKER: search limited to their own resume(s)
    - NOT interpreted as NOT(OR(...))
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if institution_name:
        conditions.append(JobSeekerEducation.institution_name.ilike(f"%{institution_name}%"))
    if degree is not None:
        deg = degree.value if hasattr(degree, "value") else degree
        conditions.append(JobSeekerEducation.degree == deg)
    if study_field:
        conditions.append(JobSeekerEducation.study_field.ilike(f"%{study_field}%"))
    if start_date is not None:
        conditions.append(JobSeekerEducation.start_date == start_date)
    if end_date is not None:
        conditions.append(JobSeekerEducation.end_date == end_date)
    if job_seeker_resume_id is not None:
        conditions.append(JobSeekerEducation.job_seeker_resume_id == job_seeker_resume_id)

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
        final_where = and_(where_clause, JobSeekerEducation.job_seeker_resume_id.in_(resume_ids))
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: no extra restriction
        final_where = where_clause

    stmt = (
        select(JobSeekerEducation)
        .where(final_where)
        .order_by(JobSeekerEducation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()


# @router.get(
#     "/job_seeker_educations/",
#     response_model=list[RelationalJobSeekerEducationPublic],
# )
# async def get_job_seeker_educations(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     jse_query = select(JobSeekerEducation).offset(offset).limit(limit).order_by(JobSeekerEducation.created_at)
#     jse = await session.exec(jse_query)
#     return jse.all()


# @router.post(
#     "/job_seeker_educations/",
#     response_model=RelationalJobSeekerEducationPublic,
# )
# async def create_job_seeker_education(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_education_create: JobSeekerEducationCreate,
# ):
#     try:
#         db_jse = JobSeekerEducation(
#             institution_name=job_seeker_education_create.institution_name,
#             degree=job_seeker_education_create.degree,
#             study_field=job_seeker_education_create.study_field,
#             start_date=job_seeker_education_create.start_date,
#             end_date=job_seeker_education_create.end_date,
#             description=job_seeker_education_create.description,
#             job_seeker_resume_id=job_seeker_education_create.job_seeker_resume_id
#         )

#         session.add(db_jse)
#         await session.commit()
#         await session.refresh(db_jse)

#         return db_jse

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد تحصیلات کارجو: "
#         )


# @router.get(
#     "/job_seeker_educations/{job_seeker_education_id}",
#     response_model=RelationalJobSeekerEducationPublic,
# )
# async def get_job_seeker_education(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_education_id: UUID,
# ):
#     jse = await session.get(JobSeekerEducation, job_seeker_education_id)
#     if not jse:
#         raise HTTPException(status_code=404, detail="تحصیلات کارجو پیدا نشد")

#     return jse


# @router.patch(
#     "/job_seeker_educations/{job_seeker_education_id}",
#     response_model=RelationalJobSeekerEducationPublic,
# )
# async def patch_job_seeker_education(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_education_id: UUID,
#         job_seeker_education_update: JobSeekerEducationUpdate,
# ):
#     jse = await session.get(JobSeekerEducation, job_seeker_education_id)
#     if not jse:
#         raise HTTPException(status_code=404, detail="تحصیلات کارجو پیدا نشد")

#     update_data = job_seeker_education_update.model_dump(exclude_unset=True)
#     jse.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(jse)

#     return jse


# @router.delete(
#     "/job_seeker_educations/{job_seeker_education_id}",
#     response_model=dict[str, str],
# )
# async def delete_job_seeker_education(
#     *,
#     session: AsyncSession = Depends(get_session),
#     job_seeker_education_id: UUID
# ):
#     jse = await session.get(JobSeekerEducation, job_seeker_education_id)
#     if not jse:
#         raise HTTPException(status_code=404, detail="تحصیلات کارجو پیدا نشد")

#     await session.delete(jse)
#     await session.commit()

#     return {"msg": "تحصیلات کارجو با موفقیت حذف شد"}


# @router.get(
#     "/job_seeker_educations/search/",
#     response_model=list[RelationalJobSeekerEducationPublic],
# )
# async def search_job_seeker_educations(
#         *,
#         session: AsyncSession = Depends(get_session),
#         institution_name: str | None = None,
#         degree: JobSeekerEducationDegree | None = None,
#         study_field: str | None = None,
#         start_date: str | None = None,
#         end_date: str | None = None,
#         job_seeker_resume_id: UUID | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if institution_name:
#         conditions.append(JobSeekerEducation.institution_name.ilike(f"%{institution_name}%"))
#     if degree:
#         conditions.append(JobSeekerEducation.degree == degree)
#     if study_field:
#         conditions.append(JobSeekerEducation.study_field.ilike(f"%{study_field}%"))
#     if start_date:
#         conditions.append(JobSeekerEducation.start_date == start_date)
#     if end_date:
#         conditions.append(JobSeekerEducation.end_date == end_date)
#     if job_seeker_resume_id:
#         conditions.append(JobSeekerEducation.job_seeker_resume_id == job_seeker_resume_id)

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(JobSeekerEducation).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(JobSeekerEducation).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(JobSeekerEducation).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     jse = result.all()
#     if not jse:
#         raise HTTPException(status_code=404, detail="تحصیلات کارجو پیدا نشد")

#     return jse
