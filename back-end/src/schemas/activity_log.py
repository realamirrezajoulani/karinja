from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

from schemas.base.activity_log import ActivityLogBase
from utilities.enumerables import ActivityLogType


class ActivityLogPublic(ActivityLogBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class ActivityLogCreate(ActivityLogBase):
    pass


class ActivityLogUpdate(SQLModel):
    type: ActivityLogType | None = Field(default=None)

    # min_length=5, max_length=256
    description: str | None = Field(default=None)

    # Present solar date
    activity_date: str | None = Field(default=None)
