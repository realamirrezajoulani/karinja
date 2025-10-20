from uuid import UUID
from sqlmodel import Field, SQLModel

from utilities.enumerables import IranProvinces, JobSeekerGender, JobSeekerMaritalStatus, JobSeekerMilitaryServiceStatus


class JobSeekerPersonalInformationBase(SQLModel):
    residence_province: IranProvinces = Field(index=True)

    # min_length=5, max_length=250
    residence_address: str | None = Field(default=None)

    marital_status: JobSeekerMaritalStatus = Field(index=True)

    # ge=(Current year) - 100, le=(Current year) - 18
    birth_year: int = Field(index=True)

    gender: JobSeekerGender = Field(...)

    military_service_status: JobSeekerMilitaryServiceStatus | None = Field(default=None)
