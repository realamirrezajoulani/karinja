from uuid import uuid4, UUID
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from sqlmodel import select, and_, or_, not_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError
import aiofiles
import imghdr
import mimetypes

from dependencies import get_session, require_roles
from models.relational_models import Image, User
from schemas.image import ImageUpdate
from schemas.relational_schemas import RelationalImagePublic
from utilities.enumerables import ImageType, LogicalOperator, UserRole
from utilities.authentication import oauth2_scheme

router = APIRouter()

# Upload settings
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Role dependencies (same roles as before)
READ_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
        UserRole.JOB_SEEKER.value,
    )
)
WRITE_ROLE_DEP = Depends(
    require_roles(
        UserRole.FULL_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.EMPLOYER.value,
        UserRole.JOB_SEEKER.value,
    )
)


def _guess_extension(filename: str, content_type: str) -> str:
    """Try to determine the file extension from filename or content-type."""
    ext = Path(filename).suffix.lower()
    if ext:
        return ext
    guessed = mimetypes.guess_extension(content_type or "")
    return (guessed or "").lower()


@router.get("/images/", response_model=list[RelationalImagePublic])
async def get_images(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """List images visible to the requester (global list).

    - FULL_ADMIN / ADMIN: see all images
    - EMPLOYER / JOB_SEEKER: see only their own images
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        stmt = select(Image).order_by(Image.created_at.desc()).offset(offset).limit(limit)
    else:
        stmt = (
            select(Image)
            .where(Image.user_id == requester_id)
            .order_by(Image.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    result = await session.exec(stmt)
    return result.all()


@router.post("/images/", response_model=RelationalImagePublic)
async def create_image(
    *,
    session: AsyncSession = Depends(get_session),
    request: Request,
    file: UploadFile = File(...),
    title: ImageType = Form(...),
    # admins may pass user_id; others will be ignored
    user_id: Optional[UUID] = Form(None),
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    """Upload an image and create the database record.

    - EMPLOYER/JOB_SEEKER: user_id is ignored and the image is assigned to the requester.
    - ADMIN/FULL_ADMIN: if user_id is provided, the image will be assigned to that user; otherwise to requester.
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    # determine target user id safely
    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        target_user_id = user_id or requester_id
        # validate target user exists
        target_user = await session.get(User, target_user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")
    else:
        target_user_id = requester_id  # enforce ownership

    # basic content-type check
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (image/*).")

    # infer extension and validate
    ext = _guess_extension(file.filename, file.content_type)
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"File extension not allowed. Allowed: {', '.join(ALLOWED_EXT)}")

    unique_name = f"{uuid4().hex}{ext}"
    dest_path = UPLOAD_DIR / unique_name

    # write file asynchronously with size limit
    size = 0
    try:
        async with aiofiles.open(dest_path, "wb") as out_file:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    await out_file.close()
                    await file.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File too large.")
                await out_file.write(chunk)
    finally:
        await file.close()

    # verify the saved file is actually an image
    if imghdr.what(dest_path) is None:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

    # store the record in the DB (store relative url)
    url_path = f"/uploads/{unique_name}"
    title_val = getattr(title, "value", title)

    try:
        db_image = Image(title=title_val, url=url_path, user_id=target_user_id)
        session.add(db_image)
        await session.commit()
        await session.refresh(db_image)
        # return full url to the client for convenience
        base = str(request.base_url).rstrip("/")
        db_image.url = f"{base}{db_image.url}"
        return db_image

    except IntegrityError:
        await session.rollback()
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Database constraint violated or duplicate.")
    except Exception as e:
        await session.rollback()
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Error creating image: {e}")


@router.get("/images/{user_id}", response_model=list[RelationalImagePublic])
async def get_images_by_user(
    *,
    session: AsyncSession = Depends(get_session),
    user_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    _user: dict = READ_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
    request: Request,
):
    """List images belonging to a specific user.

    - Admins can list any user's images.
    - Employers/JobSeekers can only list their own images (user_id must equal requester id).
    Returns full URLs for convenience.
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        if str(user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to view this user's images")

    stmt = (
        select(Image)
        .where(Image.user_id == user_id)
        .order_by(Image.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    images = result.all()

    # ensure returned URLs are absolute
    base = str(request.base_url).rstrip("/")
    for img in images:
        if img.url and img.url.startswith("/uploads/"):
            img.url = f"{base}{img.url}"
    return images


@router.patch("/images/{image_id}", response_model=RelationalImagePublic)
async def patch_image(
    *,
    session: AsyncSession = Depends(get_session),
    image_id: UUID,
    file: Optional[UploadFile] = File(None),
    title: Optional[ImageType] = Form(None),
    user_id: Optional[UUID] = Form(None),
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
    request: Request,
):
    image = await session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        if str(image.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to modify this image")

    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        if user_id is not None:
            new_user = await session.get(User, user_id)
            if not new_user:
                raise HTTPException(status_code=404, detail="Target user not found")
            image.user_id = user_id

    if title is not None:
        image.title = getattr(title, "value", title)

    if file is not None:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="فایل باید از نوع تصویر باشد (image/*).")

        ext = _guess_extension(file.filename, file.content_type)
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"پسوند فایل پشتیبانی نمی‌شود. مجاز: {', '.join(ALLOWED_EXT)}")

        unique_name = f"{uuid4().hex}{ext}"
        dest_path = UPLOAD_DIR / unique_name
        size = 0
        try:
            async with aiofiles.open(dest_path, "wb") as out_file:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_FILE_SIZE:
                        await out_file.close()
                        await file.close()
                        dest_path.unlink(missing_ok=True)
                        raise HTTPException(status_code=413, detail="حجم فایل بیش از حد مجاز است.")
                    await out_file.write(chunk)
        finally:
            await file.close()

        if imghdr.what(dest_path) is None:
            dest_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="فایل ارسال‌شده تصویر معتبری نیست.")

        try:
            prev_name = Path(image.url).name
            prev_path = UPLOAD_DIR / prev_name
            if prev_path.exists():
                prev_path.unlink(missing_ok=True)
        except Exception:
            pass

        image.url = f"/uploads/{unique_name}"

    try:
        await session.commit()
        await session.refresh(image)
        if image.url and image.url.startswith("/uploads/"):
            base = str(request.base_url).rstrip("/")
            image.url = f"{base}{image.url}"
        return image
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"خطا در بروزرسانی تصویر: {e}")


@router.delete("/images/{image_id}", response_model=dict[str, str])
async def delete_image(
    *,
    session: AsyncSession = Depends(get_session),
    image_id: UUID,
    _user: dict = WRITE_ROLE_DEP,
    _: str = Depends(oauth2_scheme),
):
    image = await session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        if str(image.user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to delete this image")

    try:
        await session.delete(image)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"خطا هنگام حذف رکورد: {e}")

    try:
        filename = Path(image.url).name
        fpath = UPLOAD_DIR / filename
        if fpath.exists():
            fpath.unlink(missing_ok=True)
    except Exception:
        pass

    return {"msg": "Image deleted successfully"}


@router.get("/users/{user_id}/images/search/", response_model=list[RelationalImagePublic])
async def search_images_by_user(
    *,
    session: AsyncSession = Depends(get_session),
    user_id: UUID,
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
    request: Request,
):
    """Search images for a specific user with role-based visibility."""
    requester_role = _user["role"]
    requester_id = _user["id"]

    if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        if str(user_id) != str(requester_id):
            raise HTTPException(status_code=403, detail="Not allowed to search this user's images")

    conditions = [Image.user_id == user_id]
    if title is not None:
        t = title.value if hasattr(title, "value") else title
        conditions.append(Image.title.ilike(f"%{t}%"))
    if url:
        conditions.append(Image.url == url)

    # combine according to operator (the user_id condition is always ANDed)
    if operator == LogicalOperator.AND:
        where_clause = and_(*conditions)
    elif operator == LogicalOperator.OR:
        # OR relative to title/url: keep user_id AND (or(...))
        user_cond = conditions[0]
        other_conds = conditions[1:]
        if not other_conds:
            where_clause = user_cond
        else:
            where_clause = and_(user_cond, or_(*other_conds))
    elif operator == LogicalOperator.NOT:
        other_conds = conditions[1:]
        if not other_conds:
            raise HTTPException(status_code=400, detail="NOT operator requires at least one non-user filter")
        where_clause = and_(conditions[0], not_(or_(*other_conds)))
    else:
        raise HTTPException(status_code=400, detail="Invalid logical operator")

    stmt = select(Image).where(where_clause).order_by(Image.created_at.desc()).offset(offset).limit(limit)
    result = await session.exec(stmt)
    images = result.all()

    base = str(request.base_url).rstrip("/")
    for img in images:
        if img.url and img.url.startswith("/uploads/"):
            img.url = f"{base}{img.url}"
    return images




# # Roles allowed to READ (includes Employer and JobSeeker)
# READ_ROLE_DEP = Depends(
#     require_roles(
#         UserRole.FULL_ADMIN.value,
#         UserRole.ADMIN.value,
#         UserRole.EMPLOYER.value,
#         UserRole.JOB_SEEKER.value,
#     )
# )

# # Roles allowed to WRITE (Employer & JobSeeker can write only their own images;
# # Admins/FullAdmin can write any)
# WRITE_ROLE_DEP = Depends(
#     require_roles(
#         UserRole.FULL_ADMIN.value,
#         UserRole.ADMIN.value,
#         UserRole.EMPLOYER.value,
#         UserRole.JOB_SEEKER.value,
#     )
# )


# @router.get(
#     "/images/",
#     response_model=list[RelationalImagePublic],
# )
# async def get_images(
#     *,
#     session: AsyncSession = Depends(get_session),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
#     _user: dict = READ_ROLE_DEP,
#     _: str = Depends(oauth2_scheme),
# ):
#     """
#     list images.
#     - FULL_ADMIN / ADMIN: see all images
#     - EMPLOYER / JOB_SEEKER: see only their own images
#     """
#     requester_role = _user["role"]
#     requester_id = _user["id"]

#     if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
#         stmt = (
#             select(Image)
#             .order_by(Image.created_at.desc())
#             .offset(offset)
#             .limit(limit)
#         )
#     else:
#         # employer / job_seeker: only own images
#         stmt = (
#             select(Image)
#             .where(Image.user_id == requester_id)
#             .order_by(Image.created_at.desc())
#             .offset(offset)
#             .limit(limit)
#         )

#     result = await session.exec(stmt)
#     return result.all()


# @router.post(
#     "/images/",
#     response_model=RelationalImagePublic,
# )
# async def create_image(
#     *,
#     session: AsyncSession = Depends(get_session),
#     image_create: ImageCreate,
#     _user: dict = WRITE_ROLE_DEP,
#     _: str = Depends(oauth2_scheme),
# ):
#     """
#     Create an image record.
#     - JOB_SEEKER / EMPLOYER: can create only for themselves (user_id overridden)
#     - ADMIN / FULL_ADMIN: can create for any user_id (validated)
#     """
#     requester_role = _user["role"]
#     requester_id = _user["id"]

#     # Determine target user_id safely (prevent privilege escalation)
#     if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
#         target_user_id = image_create.user_id or requester_id
#         # validate target user exists
#         target_user = await session.get(User, target_user_id)
#         if not target_user:
#             raise HTTPException(status_code=404, detail="Target user not found")
#     else:
#         # employer / job_seeker: force owner to requester
#         target_user_id = requester_id

#     # normalize enum-like title/type if needed
#     title_val = (
#         image_create.title.value if hasattr(image_create.title, "value") else image_create.title
#     )

#     try:
#         db_image = Image(
#             title=title_val,
#             url=image_create.url,
#             user_id=target_user_id,
#             metadata=image_create.metadata if hasattr(image_create, "metadata") else None,
#         )
#         session.add(db_image)
#         await session.commit()
#         await session.refresh(db_image)
#         return db_image

#     except IntegrityError:
#         await session.rollback()
#         raise HTTPException(status_code=409, detail="Database constraint violated or duplicate")
#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(status_code=500, detail=f"Error creating image: {e}")


# @router.get(
#     "/images/{image_id}",
#     response_model=RelationalImagePublic,
# )
# async def get_image(
#     *,
#     session: AsyncSession = Depends(get_session),
#     image_id: UUID,
#     _user: dict = READ_ROLE_DEP,
#     _: str = Depends(oauth2_scheme),
# ):
#     """
#     Retrieve single image:
#     - FULL_ADMIN / ADMIN: allowed
#     - EMPLOYER / JOB_SEEKER: only if they own the image
#     """
#     image = await session.get(Image, image_id)
#     if not image:
#         raise HTTPException(status_code=404, detail="Image not found")

#     requester_role = _user["role"]
#     requester_id = _user["id"]

#     if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
#         return image

#     if str(image.user_id) != str(requester_id):
#         raise HTTPException(status_code=403, detail="Not allowed to access this image")

#     return image


# @router.patch(
#     "/images/{image_id}",
#     response_model=RelationalImagePublic,
# )
# async def patch_image(
#     *,
#     session: AsyncSession = Depends(get_session),
#     image_id: UUID,
#     image_update: ImageUpdate,
#     _user: dict = WRITE_ROLE_DEP,
#     _: str = Depends(oauth2_scheme),
# ):
#     """
#     Update an image:
#     - FULL_ADMIN / ADMIN: can update any image (including changing user_id)
#     - EMPLOYER / JOB_SEEKER: can update only their own images and cannot change user_id
#     """
#     image = await session.get(Image, image_id)
#     if not image:
#         raise HTTPException(status_code=404, detail="Image not found")

#     requester_role = _user["role"]
#     requester_id = _user["id"]

#     # owner check for non-admins
#     if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
#         if str(image.user_id) != str(requester_id):
#             raise HTTPException(status_code=403, detail="Not allowed to modify this image")

#     update_data = image_update.model_dump(exclude_unset=True)

#     # Prevent non-admins from changing user_id
#     if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value) and "user_id" in update_data:
#         update_data.pop("user_id")

#     # Normalize enum-like title if present
#     if "title" in update_data and hasattr(update_data["title"], "value"):
#         update_data["title"] = update_data["title"].value

#     # If admin provided a new user_id, validate the target exists
#     if "user_id" in update_data:
#         new_user = await session.get(User, update_data["user_id"])
#         if not new_user:
#             raise HTTPException(status_code=404, detail="Target user not found")

#     # Apply updates
#     for field, value in update_data.items():
#         setattr(image, field, value)

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
#     _user: dict = WRITE_ROLE_DEP,
#     _: str = Depends(oauth2_scheme),
# ):
#     """
#     Delete an image:
#     - FULL_ADMIN / ADMIN: can delete any image
#     - EMPLOYER / JOB_SEEKER: can delete only their own images
#     """
#     image = await session.get(Image, image_id)
#     if not image:
#         raise HTTPException(status_code=404, detail="Image not found")

#     requester_role = _user["role"]
#     requester_id = _user["id"]

#     if requester_role not in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
#         if str(image.user_id) != str(requester_id):
#             raise HTTPException(status_code=403, detail="Not allowed to delete this image")

#     await session.delete(image)
#     await session.commit()
#     return {"msg": "Image deleted successfully"}


# @router.get(
#     "/images/search/",
#     response_model=list[RelationalImagePublic],
# )
# async def search_images(
#     *,
#     session: AsyncSession = Depends(get_session),
#     title: ImageType | None = None,
#     url: str | None = None,
#     operator: LogicalOperator = Query(
#         default=LogicalOperator.AND,
#         description="Logical operator to combine filters: AND | OR | NOT",
#     ),
#     offset: int = Query(default=0, ge=0),
#     limit: int = Query(default=100, le=100),
#     _user: dict = READ_ROLE_DEP,
#     _: str = Depends(oauth2_scheme),
# ):
#     """
#     Search images.
#     - FULL_ADMIN / ADMIN: search across all images
#     - EMPLOYER / JOB_SEEKER: search limited to their own images
#     """
#     requester_role = _user["role"]
#     requester_id = _user["id"]

#     conditions = []
#     if title is not None:
#         t = title.value if hasattr(title, "value") else title
#         # if your Image model stores title as string, compare accordingly
#         conditions.append(Image.title.ilike(f"%{t}%"))
#     if url:
#         conditions.append(Image.url == url)

#     if not conditions:
#         raise HTTPException(status_code=400, detail="No search filters provided")

#     # combine conditions according to operator
#     if operator == LogicalOperator.AND:
#         where_clause = and_(*conditions)
#     elif operator == LogicalOperator.OR:
#         where_clause = or_(*conditions)
#     elif operator == LogicalOperator.NOT:
#         where_clause = not_(or_(*conditions))
#     else:
#         raise HTTPException(status_code=400, detail="Invalid logical operator")

#     # apply role-based visibility
#     if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
#         final_where = where_clause
#     else:
#         final_where = and_(where_clause, Image.user_id == requester_id)

#     stmt = (
#         select(Image)
#         .where(final_where)
#         .order_by(Image.created_at.desc())
#         .offset(offset)
#         .limit(limit)
#     )
#     result = await session.exec(stmt)
#     return result.all()
