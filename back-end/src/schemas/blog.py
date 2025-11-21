from datetime import datetime
from sqlmodel import UUID, Column, Field, SQLModel, Text

from schemas.base.blog import BlogBase
from utilities.enumerables import BlogStatus


class BlogPublic(BlogBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class BlogCreate(BlogBase):
    user_id: UUID


class BlogUpdate(SQLModel):
    title: str | None = Field(default=None, max_length=255, index=True)
    content: str | None = Field(default=None, sa_column=Column(Text))
    status: BlogStatus | None = Field(default=None, index=True)
    views_count: int | None = Field(default=None)
    likes_count: int | None = Field(default=None)
    comments_count: int | None = Field(default=None)

    published_at: str | None = Field(default=None, index=True)
