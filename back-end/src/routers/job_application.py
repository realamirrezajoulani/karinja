from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import JobApplication, JobPosting, JobSeekerResume, User
from schemas.relational_schemas import RelationalJobApplicationPublic
from sqlmodel import and_, not_, or_, select

from schemas.job_application import JobApplicationCreate, JobApplicationUpdate
from utilities.enumerables import JobApplicationStatus, LogicalOperator, UserRole
from utilities.authentication import oauth2_scheme


router = APIRouter()


# Roles allowed to READ (includes Employer & JobSeeker)
READ_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
        UserRole.JOB_SEEKER.value,
    )
)

# Roles allowed to CREATE: JobSeeker + Admin/FullAdmin
CREATE_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.JOB_SEEKER.value,
    )
)

# Roles allowed to WRITE (patch/delete): Admin/FullAdmin always; Employer limited; JobSeeker limited
WRITE_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
        UserRole.JOB_SEEKER.value,
    )
)


@router.get(
    "/job_applications/",
    response_model=list[RelationalJobApplicationPublic],
)
async def get_job_applications(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    list job applications with role-based visibility:
    - FULL_ADMIN / ADMIN: see all applications
    - EMPLOYER: see applications for job_postings belonging to their company
    - JOB_SEEKER: see only applications they submitted (via their resumes)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        stmt = (
            select(JobApplication)
            .order_by(JobApplication.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    elif requester_role == UserRole.EMPLOYER.value:
        # Employer sees applications for their company's postings
        employer_user = await session.get(User, requester_id)
        if not employer_user:
            raise HTTPException(status_code=404, detail="Requester user not found")
        employer_company_id = getattr(employer_user, "company_id", None)
        if not employer_company_id:
            return []  # no company associated -> no applications
        # join JobPosting to filter by company_id
        stmt = (
            select(JobApplication)
            .join(JobPosting, JobApplication.job_posting_id == JobPosting.id)
            .where(JobPosting.company_id == employer_company_id)
            .order_by(JobApplication.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # JOB_SEEKER: see only own applications (lookup via resume -> user_id)
        # collect resume ids owned by requester
        resumes_stmt = select(JobSeekerResume.id).where(JobSeekerResume.user_id == requester_id)
        resume_ids = (await session.exec(resumes_stmt)).all()
        if not resume_ids:
            return []
        stmt = (
            select(JobApplication)
            .where(JobApplication.job_seeker_resume_id.in_(resume_ids))
            .order_by(JobApplication.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/job_applications/",
    response_model=RelationalJobApplicationPublic,
    dependencies=[CREATE_ROLE_DEP],
)
async def create_job_application(
    *,
    session: AsyncSession = Depends(get_session),
    job_application_create: JobApplicationCreate,
    _user: dict = Depends(require_roles(UserRole.FULL_ADMIN.value, UserRole.ADMIN.value, UserRole.JOB_SEEKER.value)),
    _: str = Depends(oauth2_scheme),
):
    """
    Create a job application:
    - JOB_SEEKER: can create only for their own resume (job_seeker_resume_id must belong to them)
    - ADMIN / FULL_ADMIN: can create for any resume_id
    - EMPLOYER: cannot create (not in CREATE_ROLE_DEP)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    # validate job_posting exists
    posting = await session.get(JobPosting, job_application_create.job_posting_id)
    if not posting:
        raise HTTPException(status_code=404, detail="Job posting not found")

    # determine resume ownership
    resume_id = job_application_create.job_seeker_resume_id
    if requester_role == UserRole.JOB_SEEKER.value:
        if resume_id is None:
            raise HTTPException(status_code=400, detail="job_seeker_resume_id is required")
        resume = await session.get(JobSeekerResume, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        if str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="You cannot apply using another user's resume")

    # Normalize status enum if provided
    status_val = (
        job_application_create.status.value
        if hasattr(job_application_create.status, "value")
        else job_application_create.status
    )

    try:
        db_job_application = JobApplication(
            application_date=job_application_create.application_date,
            status=status_val,
            cover_letter=job_application_create.cover_letter,
            job_posting_id=job_application_create.job_posting_id,
            job_seeker_resume_id=resume_id,
        )
        session.add(db_job_application)
        await session.commit()
        await session.refresh(db_job_application)
        return db_job_application

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating job application: {e}")


@router.get(
    "/job_applications/{job_application_id}",
    response_model=RelationalJobApplicationPublic,
)
async def get_job_application(
    *,
    session: AsyncSession = Depends(get_session),
    job_application_id: UUID,
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve single application with role-based access:
    - FULL_ADMIN / ADMIN: any
    - EMPLOYER: only if the application is for their company's posting
    - JOB_SEEKER: only if they submitted it (via resume)
    """
    app = await session.get(JobApplication, job_application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Job application not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        return app

    if requester_role == UserRole.EMPLOYER.value:
        employer_user = await session.get(User, requester_id)
        if not employer_user:
            raise HTTPException(status_code=404, detail="Requester user not found")
        employer_company_id = getattr(employer_user, "company_id", None)
        if not employer_company_id:
            raise HTTPException(status_code=403, detail="Employer has no associated company")
        posting = await session.get(JobPosting, app.job_posting_id)
        if not posting or str(posting.company_id) != str(employer_company_id):
            raise HTTPException(status_code=403, detail="Not allowed to access this application")
        return app

    # JOB_SEEKER
    resume = await session.get(JobSeekerResume, app.job_seeker_resume_id)
    if not resume or str(resume.user_id) != str(requester_id):
        raise HTTPException(status_code=403, detail="Not allowed to access this application")
    return app


@router.patch(
    "/job_applications/{job_application_id}",
    response_model=RelationalJobApplicationPublic,
)
async def patch_job_application(
    *,
    session: AsyncSession = Depends(get_session),
    job_application_id: UUID,
    job_application_update: JobApplicationUpdate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Update an application:
    - FULL_ADMIN / ADMIN: can update any field
    - EMPLOYER: can update only `status` for applications targeting their company's postings
    - JOB_SEEKER: can update only their own application (e.g., cover_letter); cannot change status
    """
    app = await session.get(JobApplication, job_application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Job application not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    # Ownership checks
    if requester_role == UserRole.EMPLOYER.value:
        employer_user = await session.get(User, requester_id)
        if not employer_user:
            raise HTTPException(status_code=404, detail="Requester user not found")
        employer_company_id = getattr(employer_user, "company_id", None)
        if not employer_company_id:
            raise HTTPException(status_code=403, detail="Employer has no associated company")
        posting = await session.get(JobPosting, app.job_posting_id)
        if not posting or str(posting.company_id) != str(employer_company_id):
            raise HTTPException(status_code=403, detail="Not allowed to modify this application")

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, app.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to modify this application")

    update_data = job_application_update.model_dump(exclude_unset=True)

    # Field-level permissions:
    # - JobSeeker cannot change status, job_posting_id, job_seeker_resume_id
    # - Employer can change only status
    # - Admin/FullAdmin can change anything
    if requester_role == UserRole.JOB_SEEKER.value:
        forbidden = {"status", "job_posting_id", "job_seeker_resume_id"}
        for f in forbidden:
            if f in update_data:
                raise HTTPException(status_code=403, detail=f"You cannot change `{f}`")
    elif requester_role == UserRole.EMPLOYER.value:
        # allow only 'status' updates
        allowed = {"status"}
        for f in list(update_data.keys()):
            if f not in allowed:
                raise HTTPException(status_code=403, detail=f"Employers can only change `{', '.join(allowed)}`")

    # If status provided, normalize enum
    if "status" in update_data:
        update_data["status"] = (
            update_data["status"].value if hasattr(update_data["status"], "value") else update_data["status"]
        )

    # If Admin changed job_posting_id or job_seeker_resume_id, validate existence
    if "job_posting_id" in update_data:
        new_posting = await session.get(JobPosting, update_data["job_posting_id"])
        if not new_posting:
            raise HTTPException(status_code=404, detail="Target job posting not found")
    if "job_seeker_resume_id" in update_data:
        new_resume = await session.get(JobSeekerResume, update_data["job_seeker_resume_id"])
        if not new_resume:
            raise HTTPException(status_code=404, detail="Target resume not found")

    # Apply updates
    for field, value in update_data.items():
        setattr(app, field, value)

    await session.commit()
    await session.refresh(app)
    return app


@router.delete(
    "/job_applications/{job_application_id}",
    response_model=dict[str, str],
)
async def delete_job_application(
    *,
    session: AsyncSession = Depends(get_session),
    job_application_id: UUID,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete an application:
    - FULL_ADMIN / ADMIN: can delete any
    - JOB_SEEKER: can delete only their own (withdraw)
    - EMPLOYER: cannot delete (they can change status but not delete)
    """
    app = await session.get(JobApplication, job_application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Job application not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        pass
    elif requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, app.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to delete this application")
    else:
        # EMPLOYER
        raise HTTPException(status_code=403, detail="Employers cannot delete applications")

    await session.delete(app)
    await session.commit()
    return {"msg": "Job application deleted successfully"}


@router.get(
    "/job_applications/search/",
    response_model=list[RelationalJobApplicationPublic],
)
async def search_job_applications(
    *,
    session: AsyncSession = Depends(get_session),
    application_date: str = None,
    status: JobApplicationStatus = None,
    cover_letter: str = None,
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
    Search applications with role-based visibility:
    - FULL_ADMIN / ADMIN: search across all applications
    - EMPLOYER: search applications for their company's postings
    - JOB_SEEKER: search only their own applications
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if application_date is not None:
        conditions.append(JobApplication.application_date == application_date)
    if status is not None:
        st = status.value if hasattr(status, "value") else status
        conditions.append(JobApplication.status == st)
    if cover_letter:
        conditions.append(JobApplication.cover_letter.ilike(f"%{cover_letter}%"))

    if not conditions:
        raise HTTPException(status_code=400, detail="No search filters provided")

    # combine conditions
    if operator == LogicalOperator.AND:
        where_clause = and_(*conditions)
    elif operator == LogicalOperator.OR:
        where_clause = or_(*conditions)
    elif operator == LogicalOperator.NOT:
        where_clause = not_(or_(*conditions))
    else:
        raise HTTPException(status_code=400, detail="Invalid logical operator")

    # apply role-based visibility
    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        final_where = where_clause
        stmt = (
            select(JobApplication)
            .where(final_where)
            .order_by(JobApplication.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    elif requester_role == UserRole.EMPLOYER.value:
        employer_user = await session.get(User, requester_id)
        if not employer_user:
            raise HTTPException(status_code=404, detail="Requester user not found")
        employer_company_id = getattr(employer_user, "company_id", None)
        if not employer_company_id:
            return []
        # join JobPosting to filter by company
        stmt = (
            select(JobApplication)
            .join(JobPosting, JobApplication.job_posting_id == JobPosting.id)
            .where(and_(where_clause, JobPosting.company_id == employer_company_id))
            .order_by(JobApplication.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # JOB_SEEKER: restrict to own resumes
        resumes_stmt = select(JobSeekerResume.id).where(JobSeekerResume.user_id == requester_id)
        resume_ids = (await session.exec(resumes_stmt)).all()
        if not resume_ids:
            return []
        final_where = and_(where_clause, JobApplication.job_seeker_resume_id.in_(resume_ids))
        stmt = (
            select(JobApplication)
            .where(final_where)
            .order_by(JobApplication.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()



# @router.get(
#     "/job_applications/",
#     response_model=list[RelationalJobApplicationPublic],
# )
# async def get_job_applications(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     job_applications_query = select(JobApplication).offset(offset).limit(limit).order_by(JobApplication.created_at)
#     job_applications = await session.exec(job_applications_query)
#     return job_applications.all()


# @router.post(
#     "/job_applications/",
#     response_model=RelationalJobApplicationPublic,
# )
# async def create_job_application(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_application_create: JobApplicationCreate,
# ):
#     try:
#         db_job_application = JobApplication(
#             application_date=job_application_create.application_date,
#             status=job_application_create.status,
#             cover_letter=job_application_create.cover_letter,
#             job_posting_id=job_application_create.job_posting_id,
#             job_seeker_resume_id=job_application_create.job_seeker_resume_id
#         )

#         session.add(db_job_application)
#         await session.commit()
#         await session.refresh(db_job_application)

#         return db_job_application

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد درخواست کار: "
#         )


# @router.get(
#     "/job_applications/{job_application_id}",
#     response_model=RelationalJobApplicationPublic,
# )
# async def get_job_application(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_application_id: UUID,
# ):
#     job_application = await session.get(JobApplication, job_application_id)
#     if not job_application:
#         raise HTTPException(status_code=404, detail="درخواست کار پیدا نشد")

#     return job_application


# @router.patch(
#     "/job_applications/{job_application_id}",
#     response_model=RelationalJobApplicationPublic,
# )
# async def patch_job_application(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_application_id: UUID,
#         job_application_update: JobApplicationUpdate,
# ):
#     job_application = await session.get(JobApplication, job_application_id)
#     if not job_application:
#         raise HTTPException(status_code=404, detail="درخواست کار پیدا نشد")

#     update_data = job_application_update.model_dump(exclude_unset=True)

#     job_application.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(job_application)

#     return job_application


# @router.delete(
#     "/job_applications/{job_application_id}",
#     response_model=dict[str, str],
# )
# async def delete_job_application(
#     *,
#     session: AsyncSession = Depends(get_session),
#     job_application_id: UUID,
# ):
#     job_application = await session.get(JobApplication, job_application_id)
#     if not job_application:
#         raise HTTPException(status_code=404, detail="درخواست کار پیدا نشد")

#     await session.delete(job_application)
#     await session.commit()

#     return {"msg": "درخواست کار با موفقیت حذف شد"}


# @router.get(
#     "/job_applications/search/",
#     response_model=list[RelationalJobApplicationPublic],
# )
# async def search_job_applications(
#         *,
#         session: AsyncSession = Depends(get_session),
#         application_date: str | None = None,
#         status: JobApplicationStatus | None = None,
#         cover_letter: str | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if application_date:
#         conditions.append(JobApplication.application_date == application_date)
#     if status:
#         conditions.append(JobApplication.status == status)
#     if cover_letter:
#         conditions.append(JobApplication.cover_letter.ilike(f"%{cover_letter}%"))

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(JobApplication).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(JobApplication).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(JobApplication).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     job_applications = result.all()
#     if not job_applications:
#         raise HTTPException(status_code=404, detail="درخواست کار پیدا نشد")

#     return job_applications
