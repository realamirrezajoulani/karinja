from datetime import datetime
from uuid import UUID
from sqlmodel import Field, SQLModel
from schemas.base.job_seeker_resume import JobSeekerResumeBase
from utilities.enumerables import EmploymentStatusJobSeekerResume


class JobSeekerResumePublic(JobSeekerResumeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class JobSeekerResumeCreate(JobSeekerResumeBase):
    user_id: UUID


class JobSeekerResumeUpdate(SQLModel):
    # min_length=5, max_length=30
    job_title: str | None = Field(default=None)

    # max_length=250
    professional_summary: str | None = Field(default=None)

    employment_status: EmploymentStatusJobSeekerResume | None = Field(default=None)

    is_visible: bool | None = Field(default=None)
