from uuid import UUID
from datetime import datetime
from fastapi import HTTPException
from pydantic import EmailStr, field_validator
from sqlmodel import BIGINT, Column, Field, SQLModel
from schemas.base.user import UserBase
from utilities.enumerables import UserAccountStatus, UserRole
from utilities.fields_validator import validate_password_value


class UserPublic(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class UserCreate(UserBase):
    password: str = Field(...)

    @field_validator("password")
    def validate_password(cls, value: str) -> str | HTTPException:
        return validate_password_value(value)


class UserUpdate(SQLModel):
    full_name: str | None = Field(default=None, min_length=5, max_length=30)
    
    email: EmailStr | None = Field(default=None, unique=True)

    phone: int | None = Field(
        default=None,
        ge=9000000000,
        le=9999999999,
        unique=True,
        sa_column=Column(BIGINT),
    )

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=20,
        schema_extra={"pattern": r"^[a-z]+[a-z0-9._]+[a-z]+$"},
        unique=True,
    )

    role: UserRole | None = Field(default=None)

    AccountStatus: UserAccountStatus | None = Field(default=None)
