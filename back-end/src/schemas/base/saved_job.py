from uuid import UUID
from sqlmodel import Field, SQLModel


class SavedJobBase(SQLModel):
    # Present solar date
    saved_date: str = Field(index=True)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")

    job_posting_id: UUID = Field(foreign_key="jobposting.id", ondelete="CASCADE")
