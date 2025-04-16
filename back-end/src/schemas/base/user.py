from pydantic import EmailStr
from sqlmodel import Field, SQLModel, Column, BIGINT

from utilities.enumerables import UserAccountStatus, UserRole


class UserBase(SQLModel):
    full_name: str | None = Field(default=None, min_length=5, max_length=30)
    
    email: EmailStr = Field(unique=True, index=True)

    phone: int | None = Field(
        default=None,
        ge=9000000000,
        le=9999999999,
        unique=True,
        sa_column=Column(BIGINT),
    )

    username: str = Field(
        min_length=3,
        max_length=20,
        schema_extra={"pattern": r"^[a-z]+[a-z0-9._]+[a-z]+$"},
        unique=True,
        index=True,
    )

    role: UserRole = Field(...)

    AccountStatus: UserAccountStatus = Field(...)
