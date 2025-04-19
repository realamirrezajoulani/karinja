from datetime import datetime
from uuid import UUID
from sqlmodel import Field, SQLModel
from schemas.base.saved_job import SavedJobBase


class SavedJobPublic(SavedJobBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class SavedJobCreate(SavedJobBase):
    pass


class SavedJobUpdate(SQLModel):
    # Present solar date
    saved_date: str = Field(...)
