from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession

from models.relational_models import SavedJob
from schemas.relational_schemas import RelationalSavedJobPublic
from sqlmodel import and_, not_, or_, select
from sqlalchemy.exc import IntegrityError

from schemas.saved_job import SavedJobCreate, SavedJobUpdate
from utilities.enumerables import LogicalOperator, UserRole
from utilities.authentication import oauth2_scheme


router = APIRouter()

# import your models/schemas/utils accordingly
# from .models import SavedJob
# from .schemas import RelationalSavedJobPublic, SavedJobCreate, SavedJobUpdate
# from .deps import get_session, require_roles
# from .auth import get_password_hash
# from .enums import UserRole, LogicalOperator, UserAccountStatus

# Note: these endpoints require authentication; EMPLOYERs are explicitly excluded
COMMON_ROLE_DEPENDENCY = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.JOB_SEEKER.value,
    )
)


@router.get(
    "/saved_jobs/",
    response_model=list[RelationalSavedJobPublic],
)
async def get_saved_jobs(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = COMMON_ROLE_DEPENDENCY,
    _: str = Depends(oauth2_scheme),
):
    """
    Return saved jobs:
    - FULL_ADMIN / ADMIN: all saved jobs (paginated)
    - JOB_SEEKER: only their own saved jobs
    - EMPLOYER: no access (blocked by dependency)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value:
        # JOB_SEEKER only sees their own saved jobs
        stmt = (
            select(SavedJob)
            .where(SavedJob.user_id == requester_id)
            .order_by(SavedJob.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # ADMIN or FULL_ADMIN: see all
        stmt = (
            select(SavedJob)
            .order_by(SavedJob.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/saved_jobs/",
    response_model=RelationalSavedJobPublic,
)
async def create_saved_job(
    *,
    session: AsyncSession = Depends(get_session),
    saved_job_create: SavedJobCreate,
    _user: dict = COMMON_ROLE_DEPENDENCY,
    _: str = Depends(oauth2_scheme),
):
    """
    Create a saved job:
    - JOB_SEEKER: can create only for themselves (ignore provided user_id)
    - ADMIN/FULL_ADMIN: can create for any user_id provided in payload
    - EMPLOYER: no access (blocked by dependency)
    """
    try:
        requester_role = _user["role"]
        requester_id = _user["id"]

        # Determine user_id to use (prevent privilege escalation)
        if requester_role == UserRole.JOB_SEEKER.value:
            user_id = requester_id
        else:
            # ADMIN / FULL_ADMIN can specify user_id in the payload
            user_id = saved_job_create.user_id

        db_saved_job = SavedJob(
            saved_date=saved_job_create.saved_date,
            user_id=user_id,
            job_posting_id=saved_job_create.job_posting_id,
        )

        session.add(db_saved_job)
        await session.commit()
        await session.refresh(db_saved_job)

        return db_saved_job

    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Saved job already exists or database constraint violated"
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating saved job: {e}"
        )


@router.get(
    "/saved_jobs/{saved_job_id}",
    response_model=RelationalSavedJobPublic,
)
async def get_saved_job(
    *,
    session: AsyncSession = Depends(get_session),
    saved_job_id: UUID,
    _user: dict = COMMON_ROLE_DEPENDENCY,
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve a single saved job:
    - JOB_SEEKER: only if they own it
    - ADMIN / FULL_ADMIN: allowed
    """
    saved_job = await session.get(SavedJob, saved_job_id)
    if not saved_job:
        raise HTTPException(status_code=404, detail="Saved job not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value and saved_job.user_id != requester_id:
        # hide existence of other users' resources? we return 403 (explicit)
        raise HTTPException(status_code=403, detail="Not allowed to access this saved job")

    return saved_job


@router.patch(
    "/saved_jobs/{saved_job_id}",
    response_model=RelationalSavedJobPublic,
)
async def patch_saved_job(
    *,
    session: AsyncSession = Depends(get_session),
    saved_job_id: UUID,
    saved_job_update: SavedJobUpdate,
    _user: dict = COMMON_ROLE_DEPENDENCY,
    _: str = Depends(oauth2_scheme),
):
    """
    Update a saved job:
    - JOB_SEEKER: can update only their own saved job; cannot change user_id
    - ADMIN / FULL_ADMIN: can update any saved job and can change user_id
    """
    saved_job = await session.get(SavedJob, saved_job_id)
    if not saved_job:
        raise HTTPException(status_code=404, detail="Saved job not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value and saved_job.user_id != requester_id:
        raise HTTPException(status_code=403, detail="Not allowed to modify this saved job")

    update_data = saved_job_update.model_dump(exclude_unset=True)

    # Prevent JOB_SEEKER from changing ownership
    if requester_role == UserRole.JOB_SEEKER.value and "user_id" in update_data:
        update_data.pop("user_id")

    # Apply updates safely
    for field, value in update_data.items():
        setattr(saved_job, field, value)

    await session.commit()
    await session.refresh(saved_job)
    return saved_job


@router.delete(
    "/saved_jobs/{saved_job_id}",
    response_model=dict[str, str],
)
async def delete_saved_job(
    *,
    session: AsyncSession = Depends(get_session),
    saved_job_id: UUID,
    _user: dict = COMMON_ROLE_DEPENDENCY,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete a saved job:
    - JOB_SEEKER: can delete only their own saved job
    - ADMIN / FULL_ADMIN: can delete any saved job
    - EMPLOYER: no access (blocked by dependency)
    """
    saved_job = await session.get(SavedJob, saved_job_id)
    if not saved_job:
        raise HTTPException(status_code=404, detail="Saved job not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.JOB_SEEKER.value and saved_job.user_id != requester_id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this saved job")

    await session.delete(saved_job)
    await session.commit()
    return {"msg": "Saved job deleted successfully"}


@router.get(
    "/saved_jobs/search/",
    response_model=list[RelationalSavedJobPublic],
)
async def search_saved_jobs(
    *,
    session: AsyncSession = Depends(get_session),
    saved_date: str | None = None,
    operator: LogicalOperator = Query(
        default=LogicalOperator.AND,
        description="Logical operator to combine filters: AND | OR | NOT"
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = COMMON_ROLE_DEPENDENCY,
    _: str = Depends(oauth2_scheme),
):
    """
    Search saved jobs:
    - FULL_ADMIN / ADMIN: can search across all saved jobs
    - JOB_SEEKER: search limited to their own saved jobs
    - EMPLOYER: no access (blocked by dependency)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if saved_date:
        conditions.append(SavedJob.saved_date == saved_date)

    if not conditions:
        raise HTTPException(status_code=400, detail="No search filters provided")

    # Build where clause according to operator
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
        final_where = and_(where_clause, SavedJob.user_id == requester_id)
    else:
        # ADMIN / FULL_ADMIN: no extra restriction
        final_where = where_clause

    stmt = select(SavedJob).where(final_where).order_by(SavedJob.created_at.desc()).offset(offset).limit(limit)
    result = await session.exec(stmt)
    saved_jobs = result.all()
    return saved_jobs

# @router.get(
#     "/saved_jobs/",
#     response_model=list[RelationalSavedJobPublic],
# )
# async def get_saved_jobs(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     saved_jobs_query = select(SavedJob).offset(offset).limit(limit).order_by(SavedJob.created_at)
#     saved_jobs = await session.exec(saved_jobs_query)
#     return saved_jobs.all()


# @router.post(
#     "/saved_jobs/",
#     response_model=RelationalSavedJobPublic,
# )
# async def create_saved_job(
#         *,
#         session: AsyncSession = Depends(get_session),
#         saved_job_create: SavedJobCreate,
# ):
#     try:
#         db_saved_job = SavedJob(
#             saved_date=saved_job_create.saved_date,
#             user_id=saved_job_create.user_id,
#             job_posting_id=saved_job_create.job_posting_id,
#         )

#         session.add(db_saved_job)
#         await session.commit()
#         await session.refresh(db_saved_job)

#         return db_saved_job

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد آگهی شغلی ذخیره شده: "
#         )


# @router.get(
#     "/saved_jobs/{saved_job_id}",
#     response_model=RelationalSavedJobPublic,
# )
# async def get_saved_job(
#         *,
#         session: AsyncSession = Depends(get_session),
#         saved_job_id: UUID,
# ):
#     saved_job = await session.get(SavedJob, saved_job_id)
#     if not saved_job:
#         raise HTTPException(status_code=404, detail="آگهی شغل ذخیره شده پیدا نشد")

#     return saved_job


# @router.patch(
#     "/saved_jobs/{saved_job_id}",
#     response_model=RelationalSavedJobPublic,
# )
# async def patch_saved_job(
#         *,
#         session: AsyncSession = Depends(get_session),
#         saved_job_id: UUID,
#         saved_job_update: SavedJobUpdate,
# ):
#     saved_job = await session.get(SavedJob, saved_job_id)
#     if not saved_job:
#         raise HTTPException(status_code=404, detail="آگهی شغلی ذخیره شده پیدا نشد")

#     update_data = saved_job_update.model_dump(exclude_unset=True)

#     saved_job.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(saved_job)

#     return saved_job


# @router.delete(
#     "/saved_jobs/{saved_job_id}",
#     response_model=dict[str, str],
# )
# async def delete_saved_job(
#     *,
#     session: AsyncSession = Depends(get_session),
#     saved_job_id: UUID,
# ):
#     saved_job = await session.get(SavedJob, saved_job_id)
#     if not saved_job:
#         raise HTTPException(status_code=404, detail="آگهی شغلی ذخیره شده پیدا نشد")

#     await session.delete(saved_job)
#     await session.commit()

#     return {"msg": "آگهی شغلی ذخیره شده با موفقیت حذف شد"}


# @router.get(
#     "/saved_jobs/search/",
#     response_model=list[RelationalSavedJobPublic],
# )
# async def search_saved_jobs(
#         *,
#         session: AsyncSession = Depends(get_session),
#         saved_date: str | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if saved_date:
#         conditions.append(SavedJob.saved_date == saved_date)

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(SavedJob).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(SavedJob).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(SavedJob).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر، نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     saved_jobs = result.all()
#     if not saved_jobs:
#         raise HTTPException(status_code=404, detail="آگهی شغلی ذخیره شده پیدا نشد")

#     return saved_jobs
