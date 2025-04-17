from uuid import UUID
from jdatetime import datetime as jdatetime
from sqlmodel import Field, SQLModel

from utilities.enumerables import IranProvinces, JobSeekerGender, JobSeekerMaritalStatus, JobSeekerMilitaryServiceStatus


class JobSeekerPersonalInformationBase(SQLModel):
    # min_length=5, max_length=30
    profile_image: str | None = Field(default=None)

    residence_province: IranProvinces = Field(...)

    # min_length=5, max_length=250
    residence_address: str | None = Field(default=None)

    marital_status: JobSeekerMaritalStatus = Field(...)

    # ge=(Current year) - 100, le=(Current year) - 18
    birth_year: int = Field(...)

    gender: JobSeekerGender = Field(...)

    military_service_status: JobSeekerMilitaryServiceStatus | None = Field(default=None)

    job_seeker_resume_id: UUID = Field(foreign_key="jobseekerresume.id", ondelete="CASCADE")
