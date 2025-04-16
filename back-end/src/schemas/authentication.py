from sqlmodel import Field, SQLModel


class LoginRequest(SQLModel):
    username: str = Field(...)
    password: str = Field(...)
