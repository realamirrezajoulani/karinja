from uuid import UUID
from jdatetime import datetime
from sqlmodel import Field, SQLModel

from utilities.enumerables import IranProvinces, JobSeekerGender, JobSeekerMaritalStatus, JobSeekerMilitaryServiceStatus


class JobSeekerPersonalInformationBase(SQLModel):
    profile_image: str | None = Field(default=None, min_length=5, max_length=30)

    residence_province: IranProvinces = Field()

    residence_address: str | None = Field(default=None, min_length=5, max_length=250)

    marital_status: JobSeekerMaritalStatus = Field(...)

    birth_year: int = Field(
        ge=datetime.utcnow().year - 100, 
        le=datetime.utcnow().year - 18
    )

    gender: JobSeekerGender = Field(...)

    military_service_status: JobSeekerMilitaryServiceStatus | None = Field(default=None)

    job_seeker_resume_id: UUID = Field(foreign_key="job_seeker_resume.id", ondelete="CASCADE")
