from uuid import UUID
from datetime import datetime
from sqlmodel import Field, SQLModel
from schemas.base.job_seeker_personal_information import JobSeekerPersonalInformationBase
from utilities.enumerables import IranProvinces, JobSeekerGender, JobSeekerMaritalStatus, JobSeekerMilitaryServiceStatus


class JobSeekerPersonalInformationPublic(JobSeekerPersonalInformationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class JobSeekerPersonalInformationCreate(JobSeekerPersonalInformationBase):
    job_seeker_resume_id: UUID


class JobSeekerPersonalInformationUpdate(SQLModel):
    residence_province: IranProvinces | None = Field(default=None)

    # min_length=5, max_length=250
    residence_address: str | None = Field(default=None)

    marital_status: JobSeekerMaritalStatus | None = Field(default=None)

    # ge=(Current year) - 100, le=(Current year) - 18
    birth_year: int | None = Field(default=None)

    gender: JobSeekerGender | None = Field(default=None)

    military_service_status: JobSeekerMilitaryServiceStatus | None = Field(default=None)

