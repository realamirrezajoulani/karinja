from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import ActivityLog, User
from schemas.relational_schemas import RelationalActivityLogPublic
from sqlmodel import and_, not_, or_, select

from schemas.activity_log import ActivityLogCreate, ActivityLogUpdate
from utilities.enumerables import ActivityLogType, LogicalOperator, UserRole
from utilities.authentication import oauth2_scheme


router = APIRouter()


# Only ADMIN and FULL_ADMIN can access these endpoints
ADMIN_OR_FULL_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
    )
)


@router.get(
    "/activity_logs/",
    response_model=list[RelationalActivityLogPublic],
)
async def get_activity_logs(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = ADMIN_OR_FULL_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    list activity logs with role-based visibility:
    - FULL_ADMIN: see all logs
    - ADMIN: see logs that belong to JOB_SEEKER or EMPLOYER, plus their own logs
    - other roles: no access (blocked by dependency)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.FULL_ADMIN.value:
        stmt = (
            select(ActivityLog)
            .order_by(ActivityLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # ADMIN: show logs where the target user's role is JOB_SEEKER or EMPLOYER,
        # or logs owned by the admin themself.
        stmt = (
            select(ActivityLog)
            .join(User, ActivityLog.user_id == User.id)
            .where(
                or_(
                    User.role == UserRole.JOB_SEEKER.value,
                    User.role == UserRole.EMPLOYER.value,
                    ActivityLog.user_id == requester_id,
                )
            )
            .order_by(ActivityLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/activity_logs/",
    response_model=RelationalActivityLogPublic,
)
async def create_activity_log(
    *,
    session: AsyncSession = Depends(get_session),
    activity_log_create: ActivityLogCreate,
    _user: dict = ADMIN_OR_FULL_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Create an activity log:
    - FULL_ADMIN: can create for any user
    - ADMIN: can create for JOB_SEEKER, EMPLOYER, or themselves; cannot create logs for other ADMINs or FULL_ADMIN
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    # Validate target user exists
    target_user = await session.get(User, activity_log_create.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    # Admin restrictions
    if requester_role == UserRole.ADMIN.value:
        if target_user.role == UserRole.FULL_ADMIN.value:
            raise HTTPException(status_code=403, detail="Admin cannot create logs for FULL_ADMIN users")
        if target_user.role == UserRole.ADMIN.value and str(target_user.id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Admin cannot create logs for other ADMIN users")

    # Normalize enum-like type if needed
    type_val = activity_log_create.type.value if hasattr(activity_log_create.type, "value") else activity_log_create.type

    try:
        db_activity_log = ActivityLog(
            type=type_val,
            description=activity_log_create.description,
            activity_date=activity_log_create.activity_date,
            user_id=activity_log_create.user_id,
        )
        session.add(db_activity_log)
        await session.commit()
        await session.refresh(db_activity_log)
        return db_activity_log
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating activity log: {e}")


@router.get(
    "/activity_logs/{activity_log_id}",
    response_model=RelationalActivityLogPublic,
)
async def get_activity_log(
    *,
    session: AsyncSession = Depends(get_session),
    activity_log_id: UUID,
    _user: dict = ADMIN_OR_FULL_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve single activity log:
    - FULL_ADMIN: any
    - ADMIN: only if owner is JOB_SEEKER or EMPLOYER, or the admin themself
    """
    activity_log = await session.get(ActivityLog, activity_log_id)
    if not activity_log:
        raise HTTPException(status_code=404, detail="Activity log not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    owner = await session.get(User, activity_log.user_id)
    if not owner:
        # avoid leaking; treat as not found
        raise HTTPException(status_code=404, detail="Activity log owner not found")

    if requester_role == UserRole.FULL_ADMIN.value:
        return activity_log

    # ADMIN checks
    if requester_role == UserRole.ADMIN.value:
        if owner.role in (UserRole.JOB_SEEKER.value, UserRole.EMPLOYER.value):
            return activity_log
        if str(activity_log.user_id) == str(requester_id):
            return activity_log
        raise HTTPException(status_code=403, detail="Not allowed to access this activity log")

    # Other roles blocked by dependency; should not reach here
    raise HTTPException(status_code=403, detail="Not allowed")


@router.patch(
    "/activity_logs/{activity_log_id}",
    response_model=RelationalActivityLogPublic,
)
async def patch_activity_log(
    *,
    session: AsyncSession = Depends(get_session),
    activity_log_id: UUID,
    activity_log_update: ActivityLogUpdate,
    _user: dict = ADMIN_OR_FULL_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Update an activity log:
    - FULL_ADMIN: can update any log
    - ADMIN: can update logs for JOB_SEEKER and EMPLOYER and their own logs;
             cannot update logs of other ADMINs or FULL_ADMIN users
    """
    activity_log = await session.get(ActivityLog, activity_log_id)
    if not activity_log:
        raise HTTPException(status_code=404, detail="Activity log not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    owner = await session.get(User, activity_log.user_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Activity log owner not found")

    if requester_role == UserRole.FULL_ADMIN.value:
        pass  # full access
    elif requester_role == UserRole.ADMIN.value:
        if owner.role in (UserRole.JOB_SEEKER.value, UserRole.EMPLOYER.value):
            pass
        elif str(activity_log.user_id) == str(requester_id):
            pass
        else:
            raise HTTPException(status_code=403, detail="Not allowed to modify this activity log")
    else:
        raise HTTPException(status_code=403, detail="Not allowed")

    update_data = activity_log_update.model_dump(exclude_unset=True)

    # Prevent ADMIN from reassigning a log to a FULL_ADMIN or another ADMIN
    if requester_role == UserRole.ADMIN.value and "user_id" in update_data:
        new_owner = await session.get(User, update_data["user_id"])
        if not new_owner:
            raise HTTPException(status_code=404, detail="Target user not found")
        if new_owner.role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value) and str(new_owner.id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Admin cannot reassign logs to ADMIN/FULL_ADMIN users")

    # Normalize enum-like fields if needed
    if "type" in update_data and hasattr(update_data["type"], "value"):
        update_data["type"] = update_data["type"].value

    # Apply updates
    for field, value in update_data.items():
        setattr(activity_log, field, value)

    await session.commit()
    await session.refresh(activity_log)
    return activity_log


@router.delete(
    "/activity_logs/{activity_log_id}",
    response_model=dict[str, str],
)
async def delete_activity_log(
    *,
    session: AsyncSession = Depends(get_session),
    activity_log_id: UUID,
    _user: dict = ADMIN_OR_FULL_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete an activity log:
    - FULL_ADMIN: can delete any log
    - ADMIN: can delete logs of JOB_SEEKER and EMPLOYER and their own logs;
             cannot delete logs of other ADMINs or FULL_ADMIN users
    """
    activity_log = await session.get(ActivityLog, activity_log_id)
    if not activity_log:
        raise HTTPException(status_code=404, detail="Activity log not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    owner = await session.get(User, activity_log.user_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Activity log owner not found")

    if requester_role == UserRole.FULL_ADMIN.value:
        pass
    elif requester_role == UserRole.ADMIN.value:
        if owner.role in (UserRole.JOB_SEEKER.value, UserRole.EMPLOYER.value):
            pass
        elif str(activity_log.user_id) == str(requester_id):
            pass
        else:
            raise HTTPException(status_code=403, detail="Not allowed to delete this activity log")
    else:
        raise HTTPException(status_code=403, detail="Not allowed")

    await session.delete(activity_log)
    await session.commit()
    return {"msg": "Activity log deleted successfully"}


@router.get(
    "/activity_logs/search/",
    response_model=list[RelationalActivityLogPublic],
)
async def search_activity_logs(
    *,
    session: AsyncSession = Depends(get_session),
    type: ActivityLogType | None = None,
    description: str | None = None,
    activity_date: str | None = None,
    operator: LogicalOperator = Query(
        default=LogicalOperator.AND,
        description="Logical operator to combine filters: AND | OR | NOT (NOT interpreted as NOT(OR(...)))",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = ADMIN_OR_FULL_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Search activity logs:
    - FULL_ADMIN: search across all logs
    - ADMIN: search logs for JOB_SEEKER and EMPLOYER and their own logs
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if type is not None:
        t = type.value if hasattr(type, "value") else type
        conditions.append(ActivityLog.type == t)
    if description:
        conditions.append(ActivityLog.description.ilike(f"%{description}%"))
    if activity_date is not None:
        conditions.append(ActivityLog.activity_date == activity_date)

    if not conditions:
        raise HTTPException(status_code=400, detail="No search filters provided")

    if operator == LogicalOperator.AND:
        where_clause = and_(*conditions)
    elif operator == LogicalOperator.OR:
        where_clause = or_(*conditions)
    elif operator == LogicalOperator.NOT:
        where_clause = not_(or_(*conditions))
    else:
        raise HTTPException(status_code=400, detail="Invalid logical operator")

    if requester_role == UserRole.FULL_ADMIN.value:
        final_where = where_clause
        stmt = (
            select(ActivityLog)
            .where(final_where)
            .order_by(ActivityLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # ADMIN: restrict to logs for JOB_SEEKER / EMPLOYER OR own logs
        stmt = (
            select(ActivityLog)
            .join(User, ActivityLog.user_id == User.id)
            .where(
                and_(
                    where_clause,
                    or_(
                        User.role == UserRole.JOB_SEEKER.value,
                        User.role == UserRole.EMPLOYER.value,
                        ActivityLog.user_id == requester_id,
                    ),
                )
            )
            .order_by(ActivityLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


# @router.get(
#     "/activity_logs/",
#     response_model=list[RelationalActivityLogPublic],
# )
# async def get_activity_logs(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     activity_logs_query = select(ActivityLog).offset(offset).limit(limit).order_by(ActivityLog.created_at)
#     activity_logs = await session.exec(activity_logs_query)
#     return activity_logs.all()


# @router.post(
#     "/activity_logs/",
#     response_model=RelationalActivityLogPublic,
# )
# async def create_activity_log(
#         *,
#         session: AsyncSession = Depends(get_session),
#         activity_log_create: ActivityLogCreate,
# ):
#     try:
#         db_activity_log = ActivityLog(
#             type=activity_log_create.type,
#             description=activity_log_create.description,
#             activity_date=activity_log_create.activity_date,
#             user_id=activity_log_create.user_id,
#         )

#         session.add(db_activity_log)
#         await session.commit()
#         await session.refresh(db_activity_log)

#         return db_activity_log

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد رخداد فعالیت: "
#         )


# @router.get(
#     "/activity_logs/{activity_log_id}",
#     response_model=RelationalActivityLogPublic,
# )
# async def get_activity_log(
#         *,
#         session: AsyncSession = Depends(get_session),
#         activity_log_id: UUID,
# ):
#     activity_log = await session.get(ActivityLog, activity_log_id)
#     if not activity_log:
#         raise HTTPException(status_code=404, detail="رخداد فعالیت پیدا نشد")

#     return activity_log


# @router.patch(
#     "/activity_logs/{activity_log_id}",
#     response_model=RelationalActivityLogPublic,
# )
# async def patch_activity_log(
#         *,
#         session: AsyncSession = Depends(get_session),
#         activity_log_id: UUID,
#         activity_log_update: ActivityLogUpdate,
# ):
#     activity_log = await session.get(ActivityLog, activity_log_id)
#     if not activity_log:
#         raise HTTPException(status_code=404, detail="رخداد فعالیت پیدا نشد")

#     update_data = activity_log_update.model_dump(exclude_unset=True)

#     activity_log.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(activity_log)

#     return activity_log


# @router.delete(
#     "/activity_logs/{activity_log_id}",
#     response_model=dict[str, str],
# )
# async def delete_activity_log(
#     *,
#     session: AsyncSession = Depends(get_session),
#     activity_log_id: UUID,
# ):
#     activity_log = await session.get(ActivityLog, activity_log_id)
#     if not activity_log:
#         raise HTTPException(status_code=404, detail="رخداد فعالیت پیدا نشد")

#     await session.delete(activity_log)
#     await session.commit()

#     return {"msg": "رخداد فعالیت با موفقیت حذف شد"}


# @router.get(
#     "/activity_logs/search/",
#     response_model=list[RelationalActivityLogPublic],
# )
# async def search_activity_logs(
#         *,
#         session: AsyncSession = Depends(get_session),
#         type: ActivityLogType | None = None,
#         description: str | None = None,
#         activity_date: str | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if type:
#         conditions.append(ActivityLog.type == type)
#     if description:
#         conditions.append(ActivityLog.description.ilike(f"%{description}%"))
#     if activity_date:
#         conditions.append(ActivityLog.activity_date == activity_date)
    
#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(ActivityLog).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(ActivityLog).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(ActivityLog).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     activity_logs = result.all()
#     if not activity_logs:
#         raise HTTPException(status_code=404, detail="رخداد فعالیت پیدا نشد")

#     return activity_logs
