from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import Image
from schemas.relational_schemas import RelationalImagePublic
from sqlmodel import and_, not_, or_, select

from schemas.image import ImageCreate, ImageUpdate
from utilities.enumerables import ImageType, LogicalOperator


router = APIRouter()


@router.get(
    "/images/",
    response_model=list[RelationalImagePublic],
)
async def get_images(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    images_query = select(Image).offset(offset).limit(limit).order_by(Image.created_at)
    images = await session.exec(images_query)
    return images.all()


@router.post(
    "/images/",
    response_model=RelationalImagePublic,
)
async def create_image(
        *,
        session: AsyncSession = Depends(get_session),
        image_create: ImageCreate,
):
    try:
        db_image = Image(
            title=image_create.title,
            url=image_create.url,
            user_id=image_create.phone,
        )

        session.add(db_image)
        await session.commit()
        await session.refresh(db_image)

        return db_image

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد تصویر: "
        )


@router.get(
    "/images/{image_id}",
    response_model=RelationalImagePublic,
)
async def get_image(
        *,
        session: AsyncSession = Depends(get_session),
        image_id: UUID,
):
    image = await session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="تصویر پیدا نشد")

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
):
    image = await session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="تصویر پیدا نشد")

    update_data = image_update.model_dump(exclude_unset=True)

    image.sqlmodel_update(update_data)

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
):
    image = await session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="تصویر پیدا نشد")

    await session.delete(image)
    await session.commit()

    return {"msg": "تصویر با موفقیت حذف شد"}


@router.get(
    "/images/search/",
    response_model=list[RelationalImagePublic],
)
async def search_images(
        *,
        session: AsyncSession = Depends(get_session),
        title: ImageType | None = None,
        url: str | None = None,
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if title:
        conditions.append(Image.title.ilike(f"%{title}%"))
    if url:
        conditions.append(Image.url == url)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(Image).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(Image).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(Image).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    images = result.all()
    if not images:
        raise HTTPException(status_code=404, detail="تصویر پیدا نشد")

    return images
