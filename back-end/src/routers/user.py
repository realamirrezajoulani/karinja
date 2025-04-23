from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import EmailStr

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import User
from schemas.relational_schemas import RelationalUserPublic
from sqlmodel import and_, not_, or_, select
from sqlalchemy.exc import IntegrityError

from schemas.user import UserCreate, UserUpdate
from utilities.authentication import get_password_hash
from utilities.enumerables import LogicalOperator, UserAccountStatus, UserRole


router = APIRouter()


@router.get(
    "/users/",
    response_model=list[RelationalUserPublic],
)
async def get_users(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    users_query = select(User).offset(offset).limit(limit).order_by(User.created_at)
    users = await session.exec(users_query)
    return users.all()


@router.post(
    "/users/",
    response_model=RelationalUserPublic,
)
async def create_user(
        *,
        session: AsyncSession = Depends(get_session),
        user_create: UserCreate,
):
    hashed_password = get_password_hash(user_create.password)

    try:
        db_user = User(
            full_name=user_create.username,
            email=user_create.email,
            phone=user_create.phone,
            username=user_create.username,
            role=user_create.role,
            account_status=user_create.account_status,
            password=hashed_password,
        )

        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)

        return db_user

    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="نام کاربری یا پست الکترونیکی یا شماره تلفن قبلا ثبت شده است"
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد کاربر: "
        )


@router.get(
    "/users/{user_id}",
    response_model=RelationalUserPublic,
)
async def get_user(
        *,
        session: AsyncSession = Depends(get_session),
        user_id: UUID,
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    return user


@router.patch(
    "/users/{user_id}",
    response_model=RelationalUserPublic,
)
async def patch_admin(
        *,
        session: AsyncSession = Depends(get_session),
        user_id: UUID,
        user_update: UserUpdate,
):
    admin = await session.get(User, user_id)
    if not admin:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password"] = get_password_hash(update_data["password"])

    admin.sqlmodel_update(update_data)

    await session.commit()
    await session.refresh(admin)

    return admin


@router.delete(
    "/users/{user_id}",
    response_model=dict[str, str],
)
async def delete_user(
    *,
    session: AsyncSession = Depends(get_session),
    admin_id: UUID,
):
    user = await session.get(User, admin_id)
    if not user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    await session.delete(user)
    await session.commit()

    return {"msg": "کاربر با موفقیت حذف شد"}


@router.get(
    "/admins/search/",
    response_model=list[RelationalUserPublic],
)
async def search_admins(
        *,
        session: AsyncSession = Depends(get_session),
        email: EmailStr | None = None,
        phone: str | None = None,
        username: str | None = None,
        role: UserRole | None = None,
        account_status: UserAccountStatus | None = None,
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if email:
        conditions.append(User.email == email)
    if phone:
        conditions.append(User.phone == email)
    if username:
        conditions.append(User.username.ilike(f"%{username}%"))
    if role:
        conditions.append(User.role == role)
    if account_status:
        conditions.append(User.account_status == account_status)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(User).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(User).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(User).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    users = result.all()
    if not users:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    return users
