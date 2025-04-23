from uuid import UUID
from datetime import datetime

from sqlmodel import BIGINT, Column, Field, SQLModel

from schemas.base.employer_company import CompanyBase
from utilities.enumerables import EmployerCompanyEmployeeCount, EmployerCompanyIndustry, EmployerCompanyOwnershipType, JobSeekerEducationDegree


class CompanyPublic(CompanyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(SQLModel):
    # ge=10000000, le=999999999999
    registration_number: str | None = Field(
        default=None,
        unique=True,
    )

    # min_length=5, max_length=30
    full_name: str | None = Field(default=None)

    # min_length=5, max_length=64
    summary: str | None = Field(default=None)

    industry: EmployerCompanyIndustry | None = Field(default=None)

    ownership_type: EmployerCompanyOwnershipType | None = Field(default=None)

    # pattern = https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)
    website_address: str | None = Field(default=None)

    # ge=(Present year) - 200, le=(Present year)
    founded_year: int | None = Field(default=None)

    employee_count: EmployerCompanyEmployeeCount | None = Field(default=None)

    # min_length=5, max_length=255
    address: str | None = Field(default=None)

    phone: str | None = Field(
        default=None,
        unique=True,
    )

    # min_length=30, max_length=2048
    description: str | None = Field(default=None)
