from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import Notification
from schemas.relational_schemas import RelationalNotificationPublic
from sqlmodel import and_, not_, or_, select

from schemas.notification import NotificationCreate, NotificationUpdate
from utilities.enumerables import LogicalOperator, NotificationType


router = APIRouter()


@router.get(
    "/notifications/",
    response_model=list[RelationalNotificationPublic],
)
async def get_notifications(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    notifications_query = select(Notification).offset(offset).limit(limit).order_by(Notification.created_at)
    notifications = await session.exec(notifications_query)
    return notifications.all()


@router.post(
    "/notifications/",
    response_model=RelationalNotificationPublic,
)
async def create_notification(
        *,
        session: AsyncSession = Depends(get_session),
        notification_create: NotificationCreate,
):
    try:
        db_notification = Notification(
            type=notification_create.type,
            message=notification_create.message,
            is_read=notification_create.is_read,
            user_id=notification_create.user_id
        )

        session.add(db_notification)
        await session.commit()
        await session.refresh(db_notification)

        return db_notification

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد اعلان: "
        )


@router.get(
    "/notifications/{notification_id}",
    response_model=RelationalNotificationPublic,
)
async def get_notification(
        *,
        session: AsyncSession = Depends(get_session),
        notification_id: UUID,
):
    notification = await session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="اعلان پیدا نشد")

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
):
    notification = await session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="اعلان پیدا نشد")

    update_data = notification_update.model_dump(exclude_unset=True)

    notification.sqlmodel_update(update_data)

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
):
    notification = await session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="اعلان پیدا نشد")

    await session.delete(notification)
    await session.commit()

    return {"msg": "اعلان با موفقیت حذف شد"}


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
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if type:
        conditions.append(Notification.type == type)
    if message:
        conditions.append(Notification.message.ilike(f"%{message}%"))
    if is_read:
        conditions.append(Notification.is_read == is_read)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(Notification).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(Notification).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(Notification).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    notifications = result.all()
    if not notifications:
        raise HTTPException(status_code=404, detail="اعلان پیدا نشد")

    return notifications
