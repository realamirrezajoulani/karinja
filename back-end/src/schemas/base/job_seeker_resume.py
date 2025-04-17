from uuid import UUID
from sqlmodel import Field, SQLModel

from utilities.enumerables import EmploymentStatusJobSeekerResume


class JobSeekerResumeBase(SQLModel):
    # min_length=5, max_length=30
    job_title: str = Field(...)

    # max_length=250
    professional_summary: str | None = Field(default=None)

    employment_status: EmploymentStatusJobSeekerResume = Field(...)

    is_visible: bool = Field(...)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")

