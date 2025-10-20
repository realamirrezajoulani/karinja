from uuid import UUID
from sqlmodel import Field, SQLModel

from utilities.enumerables import JobApplicationStatus


class JobApplicationBase(SQLModel):
    # Present date
    application_date: str = Field(index=True)

    # From one day to 6 months
    status: JobApplicationStatus = Field(index=True)

    # min_length=5, max_length=250
    cover_letter: str | None = Field(default=None)

