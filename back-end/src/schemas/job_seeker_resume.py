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
    pass


class JobSeekerResumeUpdate(SQLModel):
    job_title: str | None = Field(default=None, min_length=5, max_length=30)

    professional_summary: str | None = Field(default=None, max_length=250)

    employment_status: EmploymentStatusJobSeekerResume | None = Field(default=None)

    is_visible: bool | None = Field(default=None)
