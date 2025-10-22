from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import EmailStr

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession

from models.relational_models import User
from schemas.relational_schemas import RelationalUserPublic
from sqlmodel import and_, not_, or_, select
from sqlalchemy.exc import IntegrityError

from schemas.user import UserCreate, UserUpdate
from utilities.authentication import get_password_hash
from utilities.enumerables import LogicalOperator, UserAccountStatus, UserRole
from utilities.authentication import oauth2_scheme


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
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    users_query = select(User).offset(offset).limit(limit).order_by(User.created_at)

    if _user["role"] != UserRole.FULL_ADMIN.value:
        users_query.where(User.role != UserRole.FULL_ADMIN.value and User.role != UserRole.ADMIN.value)

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
        _user: dict = Depends(
            require_roles(
                UserRole.FULL_ADMIN.value,
                UserRole.ADMIN.value,
        )
    ),
):
    if _user["role"] == UserRole.ADMIN.value and user_create.role == UserRole.FULL_ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="بیا 👍"
        )
    
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
        _user: dict = Depends(
            require_roles(
                UserRole.FULL_ADMIN.value,
                UserRole.ADMIN.value,
                UserRole.EMPLOYER.value,
                UserRole.JOB_SEEKER.value
            )
        )
):
    query = select(User).where(User.id == user_id)
    if _user["role"] == UserRole.ADMIN.value:
        query.where(User.role != UserRole.FULL_ADMIN.value)
    elif _user["role"] in (UserRole.JOB_SEEKER.value, UserRole.EMPLOYER.value):
        query.where(User.role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value))

    

    user = await session.exec(query)
    if not user.one_or_none():
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    return user


@router.patch(
    "/users/{user_id}",
    response_model=RelationalUserPublic,
)
async def patch_user(
        *,
        session: AsyncSession = Depends(get_session),
        user_id: UUID,
        user_update: UserUpdate,
        _user: dict = Depends(
            require_roles(
                UserRole.FULL_ADMIN.value,
                UserRole.ADMIN.value,
                UserRole.EMPLOYER.value,
                UserRole.JOB_SEEKER.value
            )
        )
):
    result = await session.exec(select(User).where(User.id == user_id))
    target_user = result.one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    requester_role = _user["role"]
    requester_id_str = str(_user["id"])
    target_id_str = str(target_user.id)

    if requester_role == UserRole.ADMIN.value:
        if target_id_str != requester_id_str and target_user.role not in (
            UserRole.JOB_SEEKER.value,
            UserRole.EMPLOYER.value,
        ):
            raise HTTPException(
                status_code=403,
                detail="ادمین فقط مجاز به ویرایش خودش یا کاربران با نقش JOB_SEEKER/EMPLOYER است"
            )
        if target_user.role == UserRole.FULL_ADMIN.value and target_id_str != requester_id_str:
            raise HTTPException(
                status_code=403,
                detail="شما اجازه ویرایش یک FULL_ADMIN را ندارید"
            )

    elif requester_role in (UserRole.JOB_SEEKER.value, UserRole.EMPLOYER.value):
        if target_id_str != requester_id_str:
            raise HTTPException(
                status_code=403,
                detail="شما اجازه ویرایش کاربر دیگری را ندارید"
            )

    update_data = user_update.model_dump(exclude_unset=True)

    if "password" in update_data:
        update_data["password"] = get_password_hash(update_data["password"])

    if requester_role != UserRole.FULL_ADMIN.value:
        forbidden_fields = {"role", "account_status"}

        for f in forbidden_fields:
            if f in update_data:
                update_data.pop(f)

    else:
        if "role" in update_data:
            new_role = update_data["role"]
            if new_role not in {r.value for r in UserRole}:
                raise HTTPException(status_code=400, detail="نقش نامعتبر است")

    for field, value in update_data.items():
        setattr(target_user, field, value)

    await session.commit()
    await session.refresh(target_user)

    return target_user


@router.delete(
    "/users/{user_id}",
    response_model=dict[str, str],
)
async def delete_user(
    *,
    session: AsyncSession = Depends(get_session),
    user_id: UUID,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value
        )
    )
):
    result = await session.exec(select(User).where(User.id == user_id))
    target_user = result.one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

    requester_role = _user["role"]
    requester_id_str = str(_user["id"])
    target_id_str = str(target_user.id)

    if requester_role == UserRole.ADMIN.value:
        if target_id_str != requester_id_str and target_user.role not in (
            UserRole.JOB_SEEKER.value,
            UserRole.EMPLOYER.value,
        ):
            raise HTTPException(
                status_code=403,
                detail="ادمین فقط مجاز به حذف خودش یا کاربران با نقش JOB_SEEKER/EMPLOYER است"
            )

    elif requester_role in (UserRole.JOB_SEEKER.value, UserRole.EMPLOYER.value):
        if target_id_str != requester_id_str:
            raise HTTPException(
                status_code=403,
                detail="شما اجازه حذف کاربر دیگری را ندارید"
            )

    await session.delete(target_user)
    await session.commit()

    return {"msg": "کاربر با موفقیت حذف شد"}


@router.get(
    "/users/search/",
    response_model=list[RelationalUserPublic],
)
async def search_users(
        *,
        session: AsyncSession = Depends(get_session),
        email: EmailStr | None = None,
        phone: str | None = None,
        username: str | None = None,
        role: UserRole | None = None,
        account_status: UserAccountStatus | None = None,
        _user: dict = Depends(
            require_roles(
                UserRole.FULL_ADMIN.value,
                UserRole.ADMIN.value,
                UserRole.EMPLOYER.value,
                UserRole.JOB_SEEKER.value
            )
        ),
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    # Get requester's role and id
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    # Email/phone filtering is restricted to ADMIN and FULL_ADMIN only.
    if (email or phone) and requester_role not in (UserRole.ADMIN.value, UserRole.FULL_ADMIN.value):
        raise HTTPException(
            status_code=403,
            detail="شما دسترسی برای جست و جو با email یا phone را ندارید"
        )

    # Build base filter conditions from query parameters
    conditions = []
    if email:
        conditions.append(User.email == email)
    if phone:
        conditions.append(User.phone == phone)
    if username:
        conditions.append(User.username.ilike(f"%{username}%"))
    if role:
        # compare stored role string with enum value
        conditions.append(User.role == role.value)
    if account_status:
        conditions.append(User.account_status == account_status.value)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    # Combine conditions according to the operator
    if operator == LogicalOperator.AND:
        where_clause = and_(*conditions)
    elif operator == LogicalOperator.OR:
        where_clause = or_(*conditions)
    elif operator == LogicalOperator.NOT:
        # Interpret NOT as "none of the conditions hold" => NOT(OR(...))
        where_clause = not_(or_(*conditions))
    else:
        raise HTTPException(status_code=400, detail="عملگر، نامعتبر مشخص شده است")

    # Apply role-based visibility rules:
    # - FULL_ADMIN: can see everyone (no extra filter)
    # - ADMIN: can see everyone except FULL_ADMIN
    # - EMPLOYER & JOB_SEEKER: can see only EMPLOYER and JOB_SEEKER
    if requester_role == UserRole.FULL_ADMIN.value:
        final_where = where_clause

    elif requester_role == UserRole.ADMIN.value:
        final_where = and_(where_clause, User.role != UserRole.FULL_ADMIN.value)

    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # Limit results to EMPLOYER and JOB_SEEKER only
        allowed_roles = [UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value]
        final_where = and_(where_clause, User.role.in_(allowed_roles))

        # Optional: if the caller is a JOB_SEEKER and they requested role filter explicitly,
        # ensure they don't request roles outside allowed set (we already intersected, but
        # raising an error can make intent explicit).
        if role and role.value not in allowed_roles:
            raise HTTPException(status_code=403, detail="شما نمی توانید برای این نقش درخواست جست و جو دهید")

    else:
        # Deny by default for unexpected roles
        raise HTTPException(status_code=403, detail="نقش نامعتبر است")

    # Execute the query with pagination
    query = select(User).where(final_where).offset(offset).limit(limit)
    result = await session.exec(query)
    users = result.all()

    # Return the list (may be empty)
    return users
