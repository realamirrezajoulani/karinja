from uuid import UUID
from datetime import datetime

from sqlmodel import Field, SQLModel

from schemas.base.image import ImageBase
from utilities.enumerables import ImageType

class ImagePublic(ImageBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class ImageCreate(ImageBase):
    pass


class ImageUpdate(SQLModel):
    title: ImageType | None = Field(default=None)

    # min_length=5, max_length=30
    url: str | None = Field(default=None)

