from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from dependencies import get_session, require_roles
from utilities.authentication import oauth2_scheme
from utilities.enumerables import UserRole

from models.relational_models import Setting, User
from schemas.relational_schemas import RelationalSettingPublic
from schemas.setting import SettingCreate, SettingUpdate

router = APIRouter()


@router.get(
    "/settings/",
    response_model=List[RelationalSettingPublic],
)
async def list_settings(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    # allow all authenticated roles to call; internal logic enforces visibility
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    List settings with role-based visibility:
    - FULL_ADMIN: sees all settings.
    - ADMIN: sees their own settings AND settings of users with roles EMPLOYER and JOB_SEEKER.
    - EMPLOYER / JOB_SEEKER: see only their own settings.
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    base_query = select(Setting).order_by(Setting.created_at.desc())

    if requester_role == UserRole.FULL_ADMIN.value:
        query = base_query
    elif requester_role == UserRole.ADMIN.value:
        # Admin sees their own settings or settings belonging to Employer/JobSeeker users.
        allowed_roles = [UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value]
        subq = select(User.id).where(User.role.in_(allowed_roles))
        query = base_query.where(or_(Setting.user_id == requester_id, Setting.user_id.in_(subq)))
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # Regular users see only their own settings
        query = base_query.where(Setting.user_id == requester_id)
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    query = query.offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


@router.post(
    "/settings/",
    response_model=RelationalSettingPublic,
)
async def create_setting(
    *,
    session: AsyncSession = Depends(get_session),
    setting_create: SettingCreate,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Create a new setting.
    Rules:
    - FULL_ADMIN: may create settings for any user.
    - ADMIN: may create settings for themselves and for users with roles EMPLOYER and JOB_SEEKER.
    - EMPLOYER / JOB_SEEKER: may create settings only for themselves.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    target_user_id = getattr(setting_create, "user_id", None)
    if target_user_id is None:
        # If the schema allows omitting user_id, default to requester
        target_user_id = _user["id"]

    # Enforce permissions on target_user_id
    if requester_role == UserRole.FULL_ADMIN.value:
        pass  # full permission
    elif requester_role == UserRole.ADMIN.value:
        # Admin may create for self or for Employer/JobSeeker users
        if str(target_user_id) == requester_id_str:
            pass
        else:
            target_user = await session.get(User, target_user_id)
            if not target_user:
                raise HTTPException(status_code=404, detail="Target user not found")
            if target_user.role not in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
                raise HTTPException(status_code=403, detail="Admin may only manage settings for Employer/JobSeeker users or themselves")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # regular users can only create for themselves
        if str(target_user_id) != requester_id_str:
            raise HTTPException(status_code=403, detail="You can create settings only for yourself")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    try:
        db_setting = Setting(
            key=setting_create.key,
            value=setting_create.value,
            user_id=target_user_id,
        )
        session.add(db_setting)
        await session.commit()
        await session.refresh(db_setting)
        return db_setting
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Setting could not be created due to data conflict")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating setting: {e}")


@router.get(
    "/settings/{setting_id}",
    response_model=RelationalSettingPublic,
)
async def get_setting(
    *,
    session: AsyncSession = Depends(get_session),
    setting_id: UUID,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve a single setting with role-based visibility:
    - FULL_ADMIN: can view any setting.
    - ADMIN: can view their own settings and settings of Employer/JobSeeker users.
    - EMPLOYER / JOB_SEEKER: can view only their own settings.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    result = await session.exec(select(Setting).where(Setting.id == setting_id))
    setting = result.one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    target_user = await session.get(User, setting.user_id)
    if not target_user:
        # If the user record is missing, deny access for safety
        raise HTTPException(status_code=404, detail="Setting owner not found")

    # Permission checks
    if requester_role == UserRole.FULL_ADMIN.value:
        pass
    elif requester_role == UserRole.ADMIN.value:
        if str(setting.user_id) == requester_id_str:
            pass  # admin's own setting
        elif target_user.role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
            pass  # admin may view Employer/JobSeeker settings
        else:
            raise HTTPException(status_code=403, detail="Admin can view only their own or Employer/JobSeeker settings")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        if str(setting.user_id) != requester_id_str:
            raise HTTPException(status_code=403, detail="You can view only your own settings")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    return setting


@router.patch(
    "/settings/{setting_id}",
    response_model=RelationalSettingPublic,
)
async def patch_setting(
    *,
    session: AsyncSession = Depends(get_session),
    setting_id: UUID,
    setting_update: SettingUpdate,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Update a setting.
    Rules:
    - FULL_ADMIN: can update any setting.
    - ADMIN: can update their own settings and settings of Employer/JobSeeker users.
    - EMPLOYER / JOB_SEEKER: can update only their own settings.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    result = await session.exec(select(Setting).where(Setting.id == setting_id))
    target_setting = result.one_or_none()
    if not target_setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    target_user = await session.get(User, target_setting.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Setting owner not found")

    # Permission checks
    if requester_role == UserRole.FULL_ADMIN.value:
        pass
    elif requester_role == UserRole.ADMIN.value:
        if str(target_setting.user_id) == requester_id_str:
            pass  # admin editing own
        elif target_user.role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
            pass  # admin may edit these
        else:
            raise HTTPException(status_code=403, detail="Admin cannot edit this setting")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        if str(target_setting.user_id) != requester_id_str:
            raise HTTPException(status_code=403, detail="You can edit only your own settings")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    update_data = setting_update.model_dump(exclude_unset=True)

    # Prevent non-FULL_ADMIN from changing owner (user_id)
    if "user_id" in update_data and requester_role != UserRole.FULL_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only FULL_ADMIN can change the owner of a setting")

    for field, value in update_data.items():
        setattr(target_setting, field, value)

    await session.commit()
    await session.refresh(target_setting)
    return target_setting


@router.delete(
    "/settings/{setting_id}",
    response_model=dict[str, str],
)
async def delete_setting(
    *,
    session: AsyncSession = Depends(get_session),
    setting_id: UUID,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Delete a setting.
    Rules:
    - FULL_ADMIN: can delete any setting.
    - ADMIN: can delete their own settings and settings of Employer/JobSeeker users.
    - EMPLOYER / JOB_SEEKER: can delete only their own settings.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    result = await session.exec(select(Setting).where(Setting.id == setting_id))
    target_setting = result.one_or_none()
    if not target_setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    target_user = await session.get(User, target_setting.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Setting owner not found")

    # Permission checks
    if requester_role == UserRole.FULL_ADMIN.value:
        pass
    elif requester_role == UserRole.ADMIN.value:
        if str(target_setting.user_id) == requester_id_str:
            pass  # admin deleting own
        elif target_user.role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
            pass  # admin may delete these
        else:
            raise HTTPException(status_code=403, detail="Admin cannot delete this setting")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        if str(target_setting.user_id) != requester_id_str:
            raise HTTPException(status_code=403, detail="You can delete only your own settings")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    await session.delete(target_setting)
    await session.commit()
    return {"msg": "Setting successfully deleted"}


@router.get(
    "/settings/search/",
    response_model=List[RelationalSettingPublic],
)
async def search_settings(
    *,
    session: AsyncSession = Depends(get_session),
    key: str | None = None,
    value: str | None = None,
    user_id: UUID | None = None,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    operator: str = Query("AND"),  # simple operator: "AND" or "OR" or "NOT"
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    _: str = Depends(oauth2_scheme),
):
    """
    Search settings by key, value, user_id.
    Role-based visibility:
    - FULL_ADMIN: full search across all settings.
    - ADMIN: search their own settings and settings of Employer/JobSeeker users.
    - EMPLOYER / JOB_SEEKER: search only their own settings.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    conditions = []
    if key:
        conditions.append(Setting.key.ilike(f"%{key}%"))
    if value:
        conditions.append(Setting.value.ilike(f"%{value}%"))
    if user_id:
        conditions.append(Setting.user_id == user_id)

    if not conditions:
        raise HTTPException(status_code=400, detail="No search parameters provided")

    # Combine conditions simply
    op = operator.upper()
    if op == "AND":
        where_clause = and_(*conditions)
    elif op == "OR":
        where_clause = or_(*conditions)
    elif op == "NOT":
        where_clause = ~or_(*conditions)
    else:
        raise HTTPException(status_code=400, detail="Invalid operator; use AND/OR/NOT")

    # Role-based filter
    if requester_role == UserRole.FULL_ADMIN.value:
        final_where = where_clause
    elif requester_role == UserRole.ADMIN.value:
        allowed_roles = [UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value]
        subq = select(User.id).where(User.role.in_(allowed_roles))
        final_where = and_(where_clause, or_(Setting.user_id == requester_id_str, Setting.user_id.in_(subq)))
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        final_where = and_(where_clause, Setting.user_id == requester_id_str)
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    query = select(Setting).where(final_where).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()
