from uuid import UUID
from datetime import datetime

from sqlmodel import Field, SQLModel

from schemas.base.job_seeker_education import JobSeekerEducationBase
from utilities.enumerables import JobSeekerEducationDegree


class JobSeekerEducationPublic(JobSeekerEducationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class JobSeekerEducationCreate(JobSeekerEducationBase):
    pass


class JobSeekerEducationUpdate(SQLModel):
    # min_length=5, max_length=30
    institution_name: str | None = Field(default=None)

    degree: JobSeekerEducationDegree | None = Field(default=None)

    # min_length=3, max_length=50
    study_field: str | None = Field(default=None)

    # from 40 years ago to now (Solar calendar)
    start_date: str | None = Field(default=None)

    # between 40 years ago and now (Solar calendar)
    end_date: str | None = Field(default=None)

    # min_length=5, max_length=250
    description: str | None = Field(default=None)
