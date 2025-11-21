from uuid import uuid4
from sqlmodel import UUID, Column, Field, SQLModel, Text


class CommentBase(SQLModel):
    content: str = Field(..., sa_column=Column(Text))
    is_approved: bool = Field(default=False, index=True)
    is_spam: bool = Field(default=False, index=True)
