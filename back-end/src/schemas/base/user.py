from pydantic import EmailStr
from sqlmodel import Field, SQLModel

from utilities.enumerables import UserAccountStatus, UserRole


class UserBase(SQLModel):
    # min_length=5, max_length=30
    full_name: str | None = Field(default=None)
    
    email: EmailStr = Field(unique=True, index=True)

    # ge=9000000000, le=9999999999
    phone: str | None = Field(
        default=None,
        unique=True
    )

    # pattern: ^[a-z]+[a-z0-9._]+[a-z]+$, min_length=3, max_length=20
    username: str = Field(
        unique=True,
        index=True,
    )

    role: UserRole = Field(...)

    account_status: UserAccountStatus = Field(...)
