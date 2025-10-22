from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from models.relational_models import Image, User
from schemas.relational_schemas import RelationalImagePublic
from sqlmodel import and_, not_, or_, select

from schemas.image import ImageCreate, ImageUpdate
from utilities.enumerables import ImageType, LogicalOperator, UserRole
from utilities.authentication import oauth2_scheme


router = APIRouter()



# Roles allowed to READ (includes Employer and JobSeeker)
READ_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
        UserRole.JOB_SEEKER.value,
    )
)

# Roles allowed to WRITE (Employer & JobSeeker can write only their own images;
# Admins/FullAdmin can write any)
WRITE_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
        UserRole.JOB_SEEKER.value,
    )
)


@router.get(
    "/images/",
    response_model=list[RelationalImagePublic],
)
async def get_images(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    list images.
    - FULL_ADMIN / ADMIN: see all images
    - EMPLOYER / JOB_SEEKER: see only their own images
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        stmt = (
            select(Image)
            .order_by(Image.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        # employer / job_seeker: only own images
        stmt = (
            select(Image)
            .where(Image.user_id == requester_id)
            .order_by(Image.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post(
    "/images/",
    response_model=RelationalImagePublic,
)
async def create_image(
    *,
    session: AsyncSession = Depends(get_session),
    image_create: ImageCreate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Create an image record.
    - JOB_SEEKER / EMPLOYER: can create only for themselves (user_id overridden)
    - ADMIN / FULL_ADMIN: can create for any user_id (validated)
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    # Determine target user_id safely (prevent privilege escalation)
    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        target_user_id = image_create.user_id or requester_id
        # validate target user exists
        target_user = await session.get(User, target_user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")
    else:
        # employer / job_seeker: force owner to requester
        target_user_id = requester_id

    # normalize enum-like title/type if needed
    title_val = (
        image_create.title.value if hasattr(image_create.title, "value") else image_create.title
    )

    try:
        db_image = Image(
            title=title_val,
            url=image_create.url,
            user_id=target_user_id,
            metadata=image_create.metadata if hasattr(image_create, "metadata") else None,
        )
        session.add(db_image)
        await session.commit()
        await session.refresh(db_image)
        return db_image

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating image: {e}")


@router.get(
    "/images/{image_id}",
    response_model=RelationalImagePublic,
)
async def get_image(
    *,
    session: AsyncSession = Depends(get_session),
    image_id: UUID,
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve single image:
    - FULL_ADMIN / ADMIN: allowed
    - EMPLOYER / JOB_SEEKER: only if they own the image
    """
    image = await session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        return image

    if str(image.user_id) != str(requester_id):
        raise HTTPException(status_code=403, detail="Not allowed to access this image")

    return image


@router.patch(
    "/images/{image_id}",
    response_model=RelationalImagePublic,
)
async def patch_image(
    *,
    session: AsyncSession = Depends(get_session),
    image_id: UUID,
    image_update: ImageUpdate,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Update an image:
    - FULL_ADMIN / ADMIN: can update any image (including changing user_id)
    - EMPLOYER / JOB_SEEKER: can update only their own images and cannot change user_id
    """
    image = await session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    # owner check for non-admins
    if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        if str(image.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to modify this image")

    update_data = image_update.model_dump(exclude_unset=True)

    # Prevent non-admins from changing user_id
    if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value) and "user_id" in update_data:
        update_data.pop("user_id")

    # Normalize enum-like title if present
    if "title" in update_data and hasattr(update_data["title"], "value"):
        update_data["title"] = update_data["title"].value

    # If admin provided a new user_id, validate the target exists
    if "user_id" in update_data:
        new_user = await session.get(User, update_data["user_id"])
        if not new_user:
            raise HTTPException(status_code=404, detail="Target user not found")

    # Apply updates
    for field, value in update_data.items():
        setattr(image, field, value)

    await session.commit()
    await session.refresh(image)
    return image


@router.delete(
    "/images/{image_id}",
    response_model=dict[str, str],
)
async def delete_image(
    *,
    session: AsyncSession = Depends(get_session),
    image_id: UUID,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """
    Delete an image:
    - FULL_ADMIN / ADMIN: can delete any image
    - EMPLOYER / JOB_SEEKER: can delete only their own images
    """
    image = await session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        if str(image.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to delete this image")

    await session.delete(image)
    await session.commit()
    return {"msg": "Image deleted successfully"}


@router.get(
    "/images/search/",
    response_model=list[RelationalImagePublic],
)
async def search_images(
    *,
    session: AsyncSession = Depends(get_session),
    title: ImageType | None = None,
    url: str | None = None,
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
    Search images.
    - FULL_ADMIN / ADMIN: search across all images
    - EMPLOYER / JOB_SEEKER: search limited to their own images
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    conditions = []
    if title is not None:
        t = title.value if hasattr(title, "value") else title
        # if your Image model stores title as string, compare accordingly
        conditions.append(Image.title.ilike(f"%{t}%"))
    if url:
        conditions.append(Image.url == url)

    if not conditions:
        raise HTTPException(status_code=400, detail="No search filters provided")

    # combine conditions according to operator
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
    else:
        final_where = and_(where_clause, Image.user_id == requester_id)

    stmt = (
        select(Image)
        .where(final_where)
        .order_by(Image.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return result.all()

# @router.get(
#     "/images/",
#     response_model=list[RelationalImagePublic],
# )
# async def get_images(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
# ):
#     images_query = select(Image).offset(offset).limit(limit).order_by(Image.created_at)
#     images = await session.exec(images_query)
#     return images.all()


# @router.post(
#     "/images/",
#     response_model=RelationalImagePublic,
# )
# async def create_image(
#         *,
#         session: AsyncSession = Depends(get_session),
#         image_create: ImageCreate,
# ):
#     try:
#         db_image = Image(
#             title=image_create.title,
#             url=image_create.url,
#             user_id=image_create.phone,
#         )

#         session.add(db_image)
#         await session.commit()
#         await session.refresh(db_image)

#         return db_image

#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"{e}خطا در ایجاد تصویر: "
#         )


# @router.get(
#     "/images/{image_id}",
#     response_model=RelationalImagePublic,
# )
# async def get_image(
#         *,
#         session: AsyncSession = Depends(get_session),
#         image_id: UUID,
# ):
#     image = await session.get(Image, image_id)
#     if not image:
#         raise HTTPException(status_code=404, detail="تصویر پیدا نشد")

#     return image


# @router.patch(
#     "/images/{image_id}",
#     response_model=RelationalImagePublic,
# )
# async def patch_image(
#         *,
#         session: AsyncSession = Depends(get_session),
#         image_id: UUID,
#         image_update: ImageUpdate,
# ):
#     image = await session.get(Image, image_id)
#     if not image:
#         raise HTTPException(status_code=404, detail="تصویر پیدا نشد")

#     update_data = image_update.model_dump(exclude_unset=True)

#     image.sqlmodel_update(update_data)

#     await session.commit()
#     await session.refresh(image)

#     return image


# @router.delete(
#     "/images/{image_id}",
#     response_model=dict[str, str],
# )
# async def delete_image(
#     *,
#     session: AsyncSession = Depends(get_session),
#     image_id: UUID,
# ):
#     image = await session.get(Image, image_id)
#     if not image:
#         raise HTTPException(status_code=404, detail="تصویر پیدا نشد")

#     await session.delete(image)
#     await session.commit()

#     return {"msg": "تصویر با موفقیت حذف شد"}


# @router.get(
#     "/images/search/",
#     response_model=list[RelationalImagePublic],
# )
# async def search_images(
#         *,
#         session: AsyncSession = Depends(get_session),
#         title: ImageType | None = None,
#         url: str | None = None,
#         operator: LogicalOperator,
#         offset: int = Query(default=0, ge=0),
#         limit: int = Query(default=100, le=100),
# ):
#     conditions = []
#     if title:
#         conditions.append(Image.title.ilike(f"%{title}%"))
#     if url:
#         conditions.append(Image.url == url)

#     if not conditions:
#         raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

#     if operator == LogicalOperator.AND:
#         query = select(Image).where(and_(*conditions))
#     elif operator == LogicalOperator.OR:
#         query = select(Image).where(or_(*conditions))
#     elif operator == LogicalOperator.NOT:
#         query = select(Image).where(not_(and_(*conditions)))
#     else:
#         raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

#     result = await session.exec(query.offset(offset).limit(limit))
#     images = result.all()
#     if not images:
#         raise HTTPException(status_code=404, detail="تصویر پیدا نشد")

#     return images
