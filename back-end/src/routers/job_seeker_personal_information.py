from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import JobSeekerPersonalInformation, JobSeekerResume, User
from schemas.job_seeker_personal_information import JobSeekerPersonalInformationCreate, JobSeekerPersonalInformationUpdate
from schemas.relational_schemas import RelationalJobSeekerPersonalInformationPublic
from sqlmodel import and_, not_, or_, select

from utilities.enumerables import IranProvinces, JobSeekerGender, JobSeekerMaritalStatus, JobSeekerMilitaryServiceStatus, LogicalOperator, UserRole
from utilities.authentication import oauth2_scheme


router = APIRouter()


# Roles allowed to READ (includes Employer)
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
    "/job_seeker_personal_informations/",
    response_model=list[RelationalJobSeekerPersonalInformationPublic],
)
async def get_job_seeker_personal_informations(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    List personal informations.
    - FULL_ADMIN / ADMIN: see all records
    - EMPLOYER: read-only, can see all records
    - JOB_SEEKER: see only personal information tied to their resume(s)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        # restrict to resumes owned by requester
        resumes_stmt = select(JobSeekerResume.id).where(JobSeekerResume.user_id == requester_id)
        resume_ids = (await session.exec(resumes_stmt)).all()
        if not resume_ids:
            return []
        stmt = (
            select(JobSeekerPersonalInformation)
            .where(JobSeekerPersonalInformation.job_seeker_resume_id.in_(resume_ids))
            .order_by(JobSeekerPersonalInformation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: see all
        stmt = (
            select(JobSeekerPersonalInformation)
            .order_by(JobSeekerPersonalInformation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/job_seeker_personal_informations/",
    response_model=RelationalJobSeekerPersonalInformationPublic,
)
async def create_job_seeker_personal_information(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_personal_information_create: JobSeekerPersonalInformationCreate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Create personal information.
    - JOB_SEEKER: can create only for their own resume (job_seeker_resume_id must belong to them)
    - ADMIN / FULL_ADMIN: can create for any resume_id
    - EMPLOYER: cannot create (write excluded)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    resume_id = job_seeker_personal_information_create.job_seeker_resume_id
    if requester_role == UserRole.JOB_SEEKER.value:
        if resume_id is None:
            raise HTTPException(status_code=400, detail="job_seeker_resume_id is required")
        resume = await session.get(JobSeekerResume, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        if str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="You cannot add personal information to another user's resume")

    try:
        db_jspi = JobSeekerPersonalInformation(
            residence_province=job_seeker_personal_information_create.residence_province,
            residence_address=job_seeker_personal_information_create.residence_address,
            marital_status=(
                job_seeker_personal_information_create.marital_status.value
                if hasattr(job_seeker_personal_information_create.marital_status, "value")
                else job_seeker_personal_information_create.marital_status
            ),
            birth_year=job_seeker_personal_information_create.birth_year,
            gender=(
                job_seeker_personal_information_create.gender.value
                if hasattr(job_seeker_personal_information_create.gender, "value")
                else job_seeker_personal_information_create.gender
            ),
            military_service_status=(
                job_seeker_personal_information_create.military_service_status.value
                if hasattr(job_seeker_personal_information_create.military_service_status, "value")
                else job_seeker_personal_information_create.military_service_status
            ),
            job_seeker_resume_id=resume_id,
        )

        session.add(db_jspi)
        await session.commit()
        await session.refresh(db_jspi)

        return db_jspi

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating personal information: {e}")


@router.get(
    "/job_seeker_personal_informations/{job_seeker_personal_information_id}",
    response_model=RelationalJobSeekerPersonalInformationPublic,
)
async def get_job_seeker_personal_information(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_personal_information_id: UUID,
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve a single personal information record.
    - FULL_ADMIN / ADMIN / EMPLOYER: allowed
    - JOB_SEEKER: only if this record belongs to one of their resumes
    """
    jspi = await session.get(JobSeekerPersonalInformation, job_seeker_personal_information_id)
    if not jspi:
        raise HTTPException(status_code=404, detail="Personal information not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jspi.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to access this resource")

    return jspi


@router.patch(
    "/job_seeker_personal_informations/{job_seeker_personal_information_id}",
    response_model=RelationalJobSeekerPersonalInformationPublic,
)
async def patch_job_seeker_personal_information(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_personal_information_id: UUID,
    job_seeker_personal_information_update: JobSeekerPersonalInformationUpdate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Update personal information.
    - FULL_ADMIN / ADMIN: can update any record (including job_seeker_resume_id)
    - JOB_SEEKER: can update only their own record; cannot change job_seeker_resume_id
    - EMPLOYER: cannot update (write excluded)
    """
    jspi = await session.get(JobSeekerPersonalInformation, job_seeker_personal_information_id)
    if not jspi:
        raise HTTPException(status_code=404, detail="Personal information not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jspi.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to modify this resource")

    update_data = job_seeker_personal_information_update.model_dump(exclude_unset=True)

    # Prevent JOB_SEEKER from changing ownership
    if requester_role == UserRole.JOB_SEEKER.value and "job_seeker_resume_id" in update_data:
        raise HTTPException(status_code=403, detail="You cannot change the resume_id of this record")

    # If ADMIN/FULL_ADMIN changed job_seeker_resume_id, validate the resume exists
    if "job_seeker_resume_id" in update_data:
        new_resume = await session.get(JobSeekerResume, update_data["job_seeker_resume_id"])
        if not new_resume:
            raise HTTPException(status_code=404, detail="Target resume not found")

    # Normalize enum values if provided
    enum_fields = ["marital_status", "gender", "military_service_status"]
    for ef in enum_fields:
        if ef in update_data and hasattr(update_data[ef], "value"):
            update_data[ef] = update_data[ef].value

    # Apply updates
    for field, value in update_data.items():
        setattr(jspi, field, value)

    await session.commit()
    await session.refresh(jspi)
    return jspi


@router.delete(
    "/job_seeker_personal_informations/{job_seeker_personal_information_id}",
    response_model=dict[str, str],
)
async def delete_job_seeker_personal_information(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_personal_information_id: UUID,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete personal information.
    - FULL_ADMIN / ADMIN: can delete any record
    - JOB_SEEKER: can delete only their own record
    - EMPLOYER: cannot delete (write excluded)
    """
    jspi = await session.get(JobSeekerPersonalInformation, job_seeker_personal_information_id)
    if not jspi:
        raise HTTPException(status_code=404, detail="Personal information not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        resume = await session.get(JobSeekerResume, jspi.job_seeker_resume_id)
        if not resume or str(resume.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to delete this resource")

    await session.delete(jspi)
    await session.commit()
    return {"msg": "Personal information deleted successfully"}


@router.get(
    "/job_seeker_personal_informations/search/",
    response_model=list[RelationalJobSeekerPersonalInformationPublic],
)
async def search_job_seeker_personal_informations(
    *,
    session: AsyncSession = Depends(get_session),
    residence_province: IranProvinces | None = None,
    residence_address: str | None = None,
    marital_status: JobSeekerMaritalStatus | None = None,
    birth_year: int | None = None,
    gender: JobSeekerGender | None = None,
    military_service_status: JobSeekerMilitaryServiceStatus | None = None,
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
    Search personal informations:
    - FULL_ADMIN / ADMIN / EMPLOYER: can search across all records
    - JOB_SEEKER: search limited to their own resume(s)
    - NOT interpreted as NOT(OR(...))
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if residence_province is not None:
        val = residence_province.value if hasattr(residence_province, "value") else residence_province
        conditions.append(JobSeekerPersonalInformation.residence_province == val)
    if residence_address:
        conditions.append(JobSeekerPersonalInformation.residence_address.ilike(f"%{residence_address}%"))
    if marital_status is not None:
        val = marital_status.value if hasattr(marital_status, "value") else marital_status
        conditions.append(JobSeekerPersonalInformation.marital_status == val)
    if birth_year is not None:
        conditions.append(JobSeekerPersonalInformation.birth_year == birth_year)
    if gender is not None:
        val = gender.value if hasattr(gender, "value") else gender
        conditions.append(JobSeekerPersonalInformation.gender == val)
    if military_service_status is not None:
        val = military_service_status.value if hasattr(military_service_status, "value") else military_service_status
        conditions.append(JobSeekerPersonalInformation.military_service_status == val)

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
    if requester_role == UserRole.JOB_SEEKER.value:
        # restrict to own resumes
        resumes_stmt = select(JobSeekerResume.id).where(JobSeekerResume.user_id == requester_id)
        resume_ids = (await session.exec(resumes_stmt)).all()
        if not resume_ids:
            return []
        final_where = and_(where_clause, JobSeekerPersonalInformation.job_seeker_resume_id.in_(resume_ids))
    else:
        # ADMIN / FULL_ADMIN / EMPLOYER: no extra restriction
        final_where = where_clause

    stmt = (
        select(JobSeekerPersonalInformation)
        .where(final_where)
        .order_by(JobSeekerPersonalInformation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()


# @router.get(
#     "/job_seeker_personal_informations/",
#     response_model=list[RelationalJobSeekerPersonalInformationPublic],
# )
# async def get_job_seeker_personal_informations (
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     jspis_query = select(JobSeekerPersonalInformation).offset(offset).limit(limit).order_by(JobSeekerPersonalInformation.created_at)
#     jspis = await session.exec(jspis_query)

#     return jspis.all()


# @router.post(
#     "/job_seeker_personal_informations/",
#     response_model=RelationalJobSeekerPersonalInformationPublic,
# )
# async def create_job_seeker_personal_information(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_personal_information_create: JobSeekerPersonalInformationCreate,
# ):
#     try:
#         db_jspi = JobSeekerPersonalInformation(
#             residence_province=job_seeker_personal_information_create.residence_province,
#             residence_address=job_seeker_personal_information_create.residence_address,
#             marital_status=job_seeker_personal_information_create.marital_status,
#             birth_year=job_seeker_personal_information_create.birth_year,
#             gender=job_seeker_personal_information_create.gender,
#             military_service_status=job_seeker_personal_information_create.military_service_status,
#             job_seeker_resume_id=job_seeker_personal_information_create.job_seeker_resume_id
#         )

#         session.add(db_jspi)
#         await session.commit()
#         await session.refresh(db_jspi)

#         return RelationalJobSeekerPersonalInformationPublic.model_validate(db_jspi)

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد اطلاعات کارجو: "
#         )


# @router.get(
#     "/job_seeker_personal_informations/{job_seeker_personal_information_id}",
#     response_model=RelationalJobSeekerPersonalInformationPublic,
# )
# async def get_job_seeker_personal_information(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_personal_information_id: UUID,
# ):
#     jspi = await session.get(JobSeekerPersonalInformation, job_seeker_personal_information_id)
#     if not jspi:
#         raise HTTPException(status_code=404, detail="اطلاعات کارجو پیدا نشد")

#     return jspi


# @router.patch(
#     "/job_seeker_personal_informations/{job_seeker_personal_information_id}",
#     response_model=RelationalJobSeekerPersonalInformationPublic,
# )
# async def patch_job_seeker_personal_information(
#         *,
#         session: AsyncSession = Depends(get_session),
#         job_seeker_personal_information_id: UUID,
#         job_seeker_personal_information_update: JobSeekerPersonalInformationUpdate,
# ):
#     jspi = await session.get(JobSeekerPersonalInformation, job_seeker_personal_information_id)
#     if not jspi:
#         raise HTTPException(status_code=404, detail="اطلاعات کارجو پیدا نشد")

#     update_data = job_seeker_personal_information_update.model_dump(exclude_unset=True)
#     if "password" in update_data:
#         update_data["password"] = get_password_hash(update_data["password"])

#     jspi.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(jspi)

#     return jspi


# @router.delete(
#     "/job_seeker_personal_informations/{job_seeker_personal_information_id}",
#     response_model=dict[str, str],
# )
# async def delete_user(
#     *,
#     session: AsyncSession = Depends(get_session),
#     job_seeker_personal_information_id: UUID,
# ):
#     jspi = await session.get(JobSeekerPersonalInformation, job_seeker_personal_information_id)
#     if not jspi:
#         raise HTTPException(status_code=404, detail="اطلاعات کارجو پیدا نشد")

#     await session.delete(jspi)
#     await session.commit()

#     return {"msg": "اطلاعات کارجو با موفقیت حذف شد"}


# @router.get(
#     "/job_seeker_personal_informations/search/",
#     response_model=list[RelationalJobSeekerPersonalInformationPublic],
# )
# async def search_admins(
#         *,
#         session: AsyncSession = Depends(get_session),
#         eresidence_province: IranProvinces | None = None,
#         residence_address: str | None = None,
#         marital_status: JobSeekerMaritalStatus | None = None,
#         birth_year: int | None = None,
#         gender: JobSeekerGender | None = None,
#         military_service_status: JobSeekerMilitaryServiceStatus | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if eresidence_province:
#         conditions.append(JobSeekerPersonalInformation.eresidence_province == eresidence_province)
#     if residence_address:
#         conditions.append(JobSeekerPersonalInformation.residence_address.ilike(f"%{residence_address}%"))
#     if marital_status:
#         conditions.append(JobSeekerPersonalInformation.marital_status == marital_status)
#     if birth_year:
#         conditions.append(JobSeekerPersonalInformation.birth_year == birth_year)
#     if gender:
#         conditions.append(JobSeekerPersonalInformation.gender == gender)
#     if military_service_status:
#         conditions.append(JobSeekerPersonalInformation.military_service_status == military_service_status)

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(JobSeekerPersonalInformation).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(JobSeekerPersonalInformation).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(JobSeekerPersonalInformation).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     jspis = result.all()
#     if not jspis:
#         raise HTTPException(status_code=404, detail="اطلاعات کارجو پیدا نشد")

#     return jspis
