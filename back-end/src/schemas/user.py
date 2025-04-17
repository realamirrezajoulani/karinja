from uuid import UUID
from datetime import datetime
from pydantic import EmailStr
from sqlmodel import BIGINT, Column, Field, SQLModel
from schemas.base.user import UserBase
from utilities.enumerables import UserAccountStatus, UserRole


class UserPublic(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class UserCreate(UserBase):
    password: str = Field(...)


class UserUpdate(SQLModel):
    # min_length=5, max_length=30
    full_name: str | None = Field(default=None)
    
    email: EmailStr | None = Field(default=None, unique=True)

    # ge=9000000000, le=9999999999
    phone: int | None = Field(
        default=None,
        unique=True,
        sa_column=Column(BIGINT),
    )

    # pattern: ^[a-z]+[a-z0-9._]+[a-z]+$, min_length=3, max_length=20
    username: str | None = Field(
        default=None,
        unique=True,
    )

    role: UserRole | None = Field(default=None)

    AccountStatus: UserAccountStatus | None = Field(default=None)
