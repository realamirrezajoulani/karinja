from uuid import UUID
from datetime import datetime

from sqlmodel import Field, SQLModel

from schemas.base.job_application import JobApplicationBase
from utilities.enumerables import JobApplicationStatus


class JobApplicationPublic(JobApplicationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class JobApplicationCreate(JobApplicationBase):
    job_posting_id: UUID
    job_seeker_resume_id: UUID


class JobApplicationUpdate(SQLModel):
    # Present date
    application_date: str | None = Field(default=None)

    # From one day to 6 months
    status: JobApplicationStatus | None = Field(default=None)

    # min_length=5, max_length=250
    cover_letter: str | None = Field(default=None)
