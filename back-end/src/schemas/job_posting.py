from uuid import UUID
from datetime import datetime

from sqlmodel import BIGINT, Column, Field, SQLModel

from schemas.base.job_posting import JobPostingBase
from utilities.enumerables import IranProvinces, JobPostingEmploymentType, JobPostingJobCategory, JobPostingSalaryUnit, JobPostingStatus, JobSeekerEducationDegree


class JobPostingPublic(JobPostingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class JobPostingCreate(JobPostingBase):
    company_id: UUID


class JobPostingUpdate(SQLModel):
    # min_length=5, max_length=30
    title: str | None = Field(default=None)

    location: IranProvinces | None = Field(default=None)

    # min_length=20, max_length=2048
    job_description: str | None = Field(default=None)

    employment_type: JobPostingEmploymentType | None = Field(default=None)

    # Present date
    posted_date: str | None = Field(default=None)

    # From one day to 6 months
    expiry_date: str | None = Field(default=None)

    salary_unit: JobPostingSalaryUnit | None = Field(default=None)

    # If the null value is entered, it means that the salary is negotiable
    salary_range: int | None = Field(default=None, sa_column=Column(BIGINT))

    job_categoriy: JobPostingJobCategory | None = Field(default=None)

    # ge=1, le=100
    vacancy_count: int | None = Field(default=None)

    status: JobPostingStatus = Field(default=None)
