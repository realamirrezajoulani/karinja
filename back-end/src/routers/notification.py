from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession

from models.relational_models import Notification, User
from schemas.relational_schemas import RelationalNotificationPublic
from sqlmodel import and_, not_, or_, select
from sqlalchemy.exc import IntegrityError

from schemas.notification import NotificationCreate, NotificationUpdate
from utilities.enumerables import LogicalOperator, NotificationType, UserRole
from utilities.authentication import oauth2_scheme


router = APIRouter()

# Dependency that allows all standard roles (EMPLOYER included)
ALL_ROLES_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
        UserRole.JOB_SEEKER.value,
    )
)

# Dependency for admin-only create (FULL_ADMIN + ADMIN)
ADMIN_CREATE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
    )
)


@router.get(
    "/notifications/",
    response_model=list[RelationalNotificationPublic],
)
async def get_notifications(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = ALL_ROLES_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    List notifications with role-based visibility:
    - FULL_ADMIN: see all notifications
    - ADMIN: see notifications for users with roles != FULL_ADMIN (including their own)
    - EMPLOYER / JOB_SEEKER: see only their own notifications
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    # FULL_ADMIN: unrestricted
    if requester_role == UserRole.FULL_ADMIN.value:
        stmt = (
            select(Notification)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    elif requester_role == UserRole.ADMIN.value:
        # ADMIN: can see notifications where the target user is NOT FULL_ADMIN
        # join is used to filter by target user's role
        stmt = (
            select(Notification)
            .join(User, Notification.user_id == User.id)
            .where(User.role != UserRole.FULL_ADMIN.value)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # EMPLOYER or JOB_SEEKER: only their own notifications
        stmt = (
            select(Notification)
            .where(Notification.user_id == requester_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/notifications/",
    response_model=RelationalNotificationPublic,
    dependencies=[ADMIN_CREATE_DEP],  # only FULL_ADMIN and ADMIN can call
)
async def create_notification(
    *,
    session: AsyncSession = Depends(get_session),
    notification_create: NotificationCreate,
    _user: dict = Depends(require_roles(UserRole.FULL_ADMIN.value, UserRole.ADMIN.value)),
    _: str = Depends(oauth2_scheme),
):
    """
    Create a notification:
    - FULL_ADMIN: can create notifications for any user
    - ADMIN: can create notifications for any user except FULL_ADMIN
    - JOB_SEEKER / EMPLOYER: cannot call this endpoint (blocked by dependency)
    """
    requester_role = _user["role"]

    target_user_id = notification_create.user_id

    # If requester is ADMIN, ensure target is not FULL_ADMIN
    if requester_role == UserRole.ADMIN.value:
        target_user = await session.get(User, target_user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")
        if target_user.role == UserRole.FULL_ADMIN.value:
            raise HTTPException(status_code=403, detail="Admin cannot create notifications for FULL_ADMIN users")

    try:
        db_notification = Notification(
            type=notification_create.type.value if hasattr(notification_create.type, "value") else notification_create.type,
            message=notification_create.message,
            is_read=notification_create.is_read if notification_create.is_read is not None else False,
            user_id=target_user_id,
        )
        session.add(db_notification)
        await session.commit()
        await session.refresh(db_notification)
        return db_notification

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Notification constraint violated")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating notification: {e}")


@router.get(
    "/notifications/{notification_id}",
    response_model=RelationalNotificationPublic,
)
async def get_notification(
    *,
    session: AsyncSession = Depends(get_session),
    notification_id: UUID,
    _user: dict = ALL_ROLES_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve a single notification:
    - FULL_ADMIN: can retrieve any notification
    - ADMIN: can retrieve notification unless it's owned by a FULL_ADMIN
    - EMPLOYER / JOB_SEEKER: can retrieve only their own notifications
    """
    notification = await session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role == UserRole.FULL_ADMIN.value:
        return notification

    # fetch owner role to decide
    owner = await session.get(User, notification.user_id)
    if not owner:
        # If owner missing, treat as not found (avoid leaking)
        raise HTTPException(status_code=404, detail="Notification owner not found")

    if requester_role == UserRole.ADMIN.value:
        if owner.role == UserRole.FULL_ADMIN.value:
            raise HTTPException(status_code=403, detail="Admin cannot access FULL_ADMIN notifications")
        return notification

    # EMPLOYER / JOB_SEEKER: only own notifications
    if str(notification.user_id) != str(requester_id):
        raise HTTPException(status_code=403, detail="Not allowed to access this notification")

    return notification


@router.patch(
    "/notifications/{notification_id}",
    response_model=RelationalNotificationPublic,
)
async def patch_notification(
    *,
    session: AsyncSession = Depends(get_session),
    notification_id: UUID,
    notification_update: NotificationUpdate,
    _user: dict = ALL_ROLES_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Update a notification:
    - FULL_ADMIN: can update any notification
    - ADMIN: can update notifications except those owned by FULL_ADMIN
    - EMPLOYER / JOB_SEEKER: can update only their own notifications
    - Non-FULL_ADMIN cannot change user_id to take ownership
    """
    notification = await session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    owner = await session.get(User, notification.user_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Notification owner not found")

    # permission checks
    if requester_role == UserRole.FULL_ADMIN.value:
        pass  # allowed
    elif requester_role == UserRole.ADMIN.value:
        if owner.role == UserRole.FULL_ADMIN.value:
            raise HTTPException(status_code=403, detail="Admin cannot modify FULL_ADMIN notifications")
    else:
        # EMPLOYER or JOB_SEEKER
        if str(notification.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to update this notification")

    update_data = notification_update.model_dump(exclude_unset=True)

    # Prevent non-FULL_ADMIN from modifying user_id
    if requester_role != UserRole.FULL_ADMIN.value and "user_id" in update_data:
        update_data.pop("user_id")

    # apply updates
    for field, value in update_data.items():
        if field == "type" and hasattr(value, "value"):
            setattr(notification, field, value.value)
        else:
            setattr(notification, field, value)

    await session.commit()
    await session.refresh(notification)
    return notification


@router.delete(
    "/notifications/{notification_id}",
    response_model=dict[str, str],
)
async def delete_notification(
    *,
    session: AsyncSession = Depends(get_session),
    notification_id: UUID,
    _user: dict = ALL_ROLES_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete a notification:
    - FULL_ADMIN: can delete any
    - ADMIN: can delete notifications except those owned by FULL_ADMIN
    - EMPLOYER / JOB_SEEKER: can delete only their own notifications
    """
    notification = await session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    owner = await session.get(User, notification.user_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Notification owner not found")

    if requester_role == UserRole.FULL_ADMIN.value:
        pass
    elif requester_role == UserRole.ADMIN.value:
        if owner.role == UserRole.FULL_ADMIN.value:
            raise HTTPException(status_code=403, detail="Admin cannot delete FULL_ADMIN notifications")
    else:
        # EMPLOYER or JOB_SEEKER
        if str(notification.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to delete this notification")

    await session.delete(notification)
    await session.commit()
    return {"msg": "Notification deleted successfully"}


@router.get(
    "/notifications/search/",
    response_model=list[RelationalNotificationPublic],
)
async def search_notifications(
    *,
    session: AsyncSession = Depends(get_session),
    type: NotificationType | None = None,
    message: str | None = None,
    is_read: bool | None = None,
    operator: LogicalOperator = Query(
        default=LogicalOperator.AND,
        description="Logical operator to combine filters: AND | OR | NOT",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = ALL_ROLES_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Search notifications with role-based visibility:
    - FULL_ADMIN: search across all notifications
    - ADMIN: search notifications for users with roles != FULL_ADMIN
    - EMPLOYER / JOB_SEEKER: search only within their own notifications
    - NOT is interpreted as NOT(OR(...))
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if type is not None:
        conditions.append(Notification.type == (type.value if hasattr(type, "value") else type))
    if message:
        conditions.append(Notification.message.ilike(f"%{message}%"))
    if is_read is not None:
        conditions.append(Notification.is_read == is_read)

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
    if requester_role == UserRole.FULL_ADMIN.value:
        final_where = where_clause
    elif requester_role == UserRole.ADMIN.value:
        # ADMIN: exclude notifications owned by FULL_ADMIN users
        final_where = and_(where_clause, User.role != UserRole.FULL_ADMIN.value)
        stmt = (
            select(Notification)
            .join(User, Notification.user_id == User.id)
            .where(final_where)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(stmt)
        return result.all()
    else:
        # EMPLOYER / JOB_SEEKER: only own notifications
        final_where = and_(where_clause, Notification.user_id == requester_id)

    stmt = (
        select(Notification)
        .where(final_where)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()


# @router.get(
#     "/notifications/",
#     response_model=list[RelationalNotificationPublic],
# )
# async def get_notifications(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     notifications_query = select(Notification).offset(offset).limit(limit).order_by(Notification.created_at)
#     notifications = await session.exec(notifications_query)
#     return notifications.all()


# @router.post(
#     "/notifications/",
#     response_model=RelationalNotificationPublic,
# )
# async def create_notification(
#         *,
#         session: AsyncSession = Depends(get_session),
#         notification_create: NotificationCreate,
# ):
#     try:
#         db_notification = Notification(
#             type=notification_create.type,
#             message=notification_create.message,
#             is_read=notification_create.is_read,
#             user_id=notification_create.user_id
#         )

#         session.add(db_notification)
#         await session.commit()
#         await session.refresh(db_notification)

#         return db_notification

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد اعلان: "
#         )


# @router.get(
#     "/notifications/{notification_id}",
#     response_model=RelationalNotificationPublic,
# )
# async def get_notification(
#         *,
#         session: AsyncSession = Depends(get_session),
#         notification_id: UUID,
# ):
#     notification = await session.get(Notification, notification_id)
#     if not notification:
#         raise HTTPException(status_code=404, detail="اعلان پیدا نشد")

#     return notification


# @router.patch(
#     "/notifications/{notification_id}",
#     response_model=RelationalNotificationPublic,
# )
# async def patch_notification(
#         *,
#         session: AsyncSession = Depends(get_session),
#         notification_id: UUID,
#         notification_update: NotificationUpdate,
# ):
#     notification = await session.get(Notification, notification_id)
#     if not notification:
#         raise HTTPException(status_code=404, detail="اعلان پیدا نشد")

#     update_data = notification_update.model_dump(exclude_unset=True)

#     notification.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(notification)

#     return notification


# @router.delete(
#     "/notifications/{notification_id}",
#     response_model=dict[str, str],
# )
# async def delete_notification(
#     *,
#     session: AsyncSession = Depends(get_session),
#     notification_id: UUID,
# ):
#     notification = await session.get(Notification, notification_id)
#     if not notification:
#         raise HTTPException(status_code=404, detail="اعلان پیدا نشد")

#     await session.delete(notification)
#     await session.commit()

#     return {"msg": "اعلان با موفقیت حذف شد"}


# @router.get(
#     "/notifications/search/",
#     response_model=list[RelationalNotificationPublic],
# )
# async def search_notifications(
#         *,
#         session: AsyncSession = Depends(get_session),
#         type: NotificationType | None = None,
#         message: str | None = None,
#         is_read: bool | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if type:
#         conditions.append(Notification.type == type)
#     if message:
#         conditions.append(Notification.message.ilike(f"%{message}%"))
#     if is_read:
#         conditions.append(Notification.is_read == is_read)

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(Notification).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(Notification).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(Notification).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     notifications = result.all()
#     if not notifications:
#         raise HTTPException(status_code=404, detail="اعلان پیدا نشد")

#     return notifications
