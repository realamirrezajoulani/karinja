from uuid import UUID
from sqlmodel import Field, SQLModel

from utilities.enumerables import EmployerCompanyEmployeeCount, EmployerCompanyIndustry, EmployerCompanyOwnershipType


class CompanyBase(SQLModel):
    # ge=10000000, le=999999999999
    registration_number: str = Field(
        unique=True
    )

    # min_length=5, max_length=30
    full_name: str = Field(...)

    # min_length=5, max_length=64
    summary: str | None = Field(default=None)

    industry: EmployerCompanyIndustry = Field(index=True)

    ownership_type: EmployerCompanyOwnershipType = Field(index=True)

    # pattern = https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)
    website_address: str | None = Field(default=None)

    # ge=(Present year) - 200, le=(Present year)
    founded_year: int = Field(index=True)

    employee_count: EmployerCompanyEmployeeCount = Field(...)

    # min_length=5, max_length=255
    address: str = Field(...)

    phone: str = Field(
        unique=True
    )

    # min_length=30, max_length=2048
    description: str = Field(...)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")



