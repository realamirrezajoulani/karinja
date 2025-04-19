from datetime import datetime
from uuid import UUID
from sqlmodel import Field, SQLModel
from schemas.base.notification import NotificationBase
from utilities.enumerables import NotificationType


class NotificationPublic(NotificationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class NotificationCreate(NotificationBase):
    pass


class JobSeekerWorkExperienceUpdate(SQLModel):
    type: NotificationType = Field(...)

    # min_length=5, max_length=50
    message: str = Field(...)

    is_read: bool = Field(...)
