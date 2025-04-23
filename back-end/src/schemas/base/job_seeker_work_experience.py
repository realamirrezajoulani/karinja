from uuid import UUID
from sqlmodel import Field, SQLModel


class JobSeekerWorkExperienceBase(SQLModel):
    # min_length=5, max_length=30
    title: str = Field(...)

    # min_length=5, max_length=30
    company_name: str = Field(...)

    # from 50 years ago to now (Solar date)
    start_date: str = Field(...)

    # between 50 years ago and now (Solar date)
    end_date: str | None = Field(default=None)

    # min_length=5, max_length=250
    description: str | None = Field(default=None)

    job_seeker_resume_id: UUID = Field(foreign_key="jobseekerresume.id", ondelete="CASCADE")
