from datetime import datetime
from uuid import UUID
from sqlmodel import Field, SQLModel
from schemas.base.job_seeker_work_experience import JobSeekerWorkExperienceBase


class JobSeekerWorkExperiencePublic(JobSeekerWorkExperienceBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class JobSeekerWorkExperienceCreate(JobSeekerWorkExperienceBase):
    job_seeker_resume_id: UUID


class JobSeekerWorkExperienceUpdate(SQLModel):
    # min_length=5, max_length=30
    title: str | None = Field(default=None)

    # min_length=5, max_length=30
    company_name: str | None = Field(default=None)

    # Can be entered from 50 years ago to the present (Solar date)
    start_date: str | None = Field(default=None)

    # Can be entered between 50 years ago and present (Solar date)
    end_date: str | None = Field(default=None)

    # min_length=5, max_length=250
    description: str | None = Field(default=None)
