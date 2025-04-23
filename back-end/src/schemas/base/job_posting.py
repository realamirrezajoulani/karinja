from uuid import UUID
from sqlmodel import BIGINT, Column, Field, SQLModel

from utilities.enumerables import IranProvinces, JobPostingEmploymentType, JobPostingJobCategory, JobPostingSalaryUnit, JobPostingStatus


class JobPostingBase(SQLModel):
    # min_length=5, max_length=30
    title: str = Field(index=True)

    location: IranProvinces = Field(index=True)

    # min_length=20, max_length=2048
    job_description: str = Field(...)

    employment_type: JobPostingEmploymentType = Field(...)

    # Present date
    posted_date: str = Field(...)

    # From one day to 6 months
    expiry_date: str | None = Field(default=None)

    salary_unit: JobPostingSalaryUnit = Field(...)

    # If the null value is entered, it means that the salary is negotiable
    salary_range: int | None = Field(default=None, sa_column=Column(BIGINT))

    job_categoriy: JobPostingJobCategory = Field(index=True)

    # ge=1, le=100
    vacancy_count: int = Field(...)

    status: JobPostingStatus = Field(...)

    company_id: UUID = Field(foreign_key="company.id", ondelete="CASCADE")

