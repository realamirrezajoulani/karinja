from uuid import UUID
from sqlmodel import Field, SQLModel

from utilities.enumerables import JobSeekerEducationDegree


class JobSeekerEducationBase(SQLModel):
    # min_length=5, max_length=30
    institution_name: str = Field(...)

    Degree: JobSeekerEducationDegree = Field(...)

    # min_length=3, max_length=50
    StudyField: str = Field(...)

    # from 40 years ago to now (Solar calendar)
    start_date: str = Field(...)

    # between 40 years ago and now (Solar calendar)
    end_date: str | None = Field(default=None)

    # min_length=5, max_length=250
    description: str | None = Field(default=None)

    job_seeker_resume_id: UUID = Field(foreign_key="jobseekerresume.id", ondelete="CASCADE")
