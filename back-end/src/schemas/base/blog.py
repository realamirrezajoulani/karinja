from sqlmodel import Column, Field, SQLModel, Text

from utilities.enumerables import BlogStatus


class BlogBase(SQLModel):
    title: str = Field(..., max_length=255, index=True)
    content: str = Field(..., sa_column=Column(Text))
    status: BlogStatus = Field(default=BlogStatus.DRAFT, index=True)
    views_count: int = Field(default=0)
    likes_count: int = Field(default=0)
    comments_count: int = Field(default=0)

    published_at: str | None = Field(default=None, index=True)
