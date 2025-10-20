from uuid import UUID
from sqlmodel import Field, SQLModel


class SavedJobBase(SQLModel):
    # Present solar date
    saved_date: str = Field(index=True)

