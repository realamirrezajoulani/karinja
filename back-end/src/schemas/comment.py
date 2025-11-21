from uuid import UUID
from datetime import datetime
from sqlmodel import Column, Field, SQLModel, Text

from schemas.base.comment import CommentBase


class CommentPublic(CommentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class CommentCreate(CommentBase):
    blog_id: UUID
    user_id: UUID


class CommentUpdate(SQLModel):
    content: str | None = Field(default=None, sa_column=Column(Text))
    is_approved: bool | None = Field(default=None, index=True)
    is_spam: bool | None = Field(default=None, index=True)
