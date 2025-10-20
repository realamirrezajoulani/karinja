from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import ActivityLog
from schemas.relational_schemas import RelationalActivityLogPublic
from sqlmodel import and_, not_, or_, select

from schemas.activity_log import ActivityLogCreate, ActivityLogUpdate
from utilities.enumerables import ActivityLogType, LogicalOperator


router = APIRouter()


@router.get(
    "/activity_logs/",
    response_model=list[RelationalActivityLogPublic],
)
async def get_activity_logs(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    activity_logs_query = select(ActivityLog).offset(offset).limit(limit).order_by(ActivityLog.created_at)
    activity_logs = await session.exec(activity_logs_query)
    return activity_logs.all()


@router.post(
    "/activity_logs/",
    response_model=RelationalActivityLogPublic,
)
async def create_activity_log(
        *,
        session: AsyncSession = Depends(get_session),
        activity_log_create: ActivityLogCreate,
):
    try:
        db_activity_log = ActivityLog(
            type=activity_log_create.type,
            description=activity_log_create.description,
            activity_date=activity_log_create.activity_date,
            user_id=activity_log_create.user_id,
        )

        session.add(db_activity_log)
        await session.commit()
        await session.refresh(db_activity_log)

        return db_activity_log

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد رخداد فعالیت: "
        )


@router.get(
    "/activity_logs/{activity_log_id}",
    response_model=RelationalActivityLogPublic,
)
async def get_activity_log(
        *,
        session: AsyncSession = Depends(get_session),
        activity_log_id: UUID,
):
    activity_log = await session.get(ActivityLog, activity_log_id)
    if not activity_log:
        raise HTTPException(status_code=404, detail="رخداد فعالیت پیدا نشد")

    return activity_log


@router.patch(
    "/activity_logs/{activity_log_id}",
    response_model=RelationalActivityLogPublic,
)
async def patch_activity_log(
        *,
        session: AsyncSession = Depends(get_session),
        activity_log_id: UUID,
        activity_log_update: ActivityLogUpdate,
):
    activity_log = await session.get(ActivityLog, activity_log_id)
    if not activity_log:
        raise HTTPException(status_code=404, detail="رخداد فعالیت پیدا نشد")

    update_data = activity_log_update.model_dump(exclude_unset=True)

    activity_log.sqlmodel_update(update_data)

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
):
    activity_log = await session.get(ActivityLog, activity_log_id)
    if not activity_log:
        raise HTTPException(status_code=404, detail="رخداد فعالیت پیدا نشد")

    await session.delete(activity_log)
    await session.commit()

    return {"msg": "رخداد فعالیت با موفقیت حذف شد"}


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
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if type:
        conditions.append(ActivityLog.type == type)
    if description:
        conditions.append(ActivityLog.description.ilike(f"%{description}%"))
    if activity_date:
        conditions.append(ActivityLog.activity_date == activity_date)
    
    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(ActivityLog).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(ActivityLog).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(ActivityLog).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    activity_logs = result.all()
    if not activity_logs:
        raise HTTPException(status_code=404, detail="رخداد فعالیت پیدا نشد")

    return activity_logs
