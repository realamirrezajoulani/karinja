from uuid import UUID
from sqlmodel import SQLModel, Field

from utilities.enumerables import ActivityLogType


class ActivityLogBase(SQLModel):
    type: ActivityLogType = Field(index=True)

    # min_length=5, max_length=256
    description: str | None = Field(default=None)

    # Present solar date
    activity_date: str = Field(index=True)

