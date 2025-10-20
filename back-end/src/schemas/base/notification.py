from uuid import UUID
from sqlmodel import Field, SQLModel

from utilities.enumerables import NotificationType


class NotificationBase(SQLModel):
    type: NotificationType = Field(index=True)

    # min_length=5, max_length=50
    message: str = Field(...)

    is_read: bool = Field(...)
