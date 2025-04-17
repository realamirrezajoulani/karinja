from uuid import UUID
from sqlmodel import Field, SQLModel

from utilities.enumerables import ImageType


class ImageBase(SQLModel):
    title: ImageType = Field(...)

    # min_length=5, max_length=30
    url: str = Field(...)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")
