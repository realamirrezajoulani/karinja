from uuid import UUID
from sqlmodel import Field, SQLModel

from utilities.enumerables import EmploymentStatusJobSeekerResume


class JobSeekerResumeBase(SQLModel):
    job_title: str = Field(min_length=5, max_length=30)

    professional_summary: str | None = Field(default=None, max_length=250)

    employment_status: EmploymentStatusJobSeekerResume = Field(...)

    is_visible: bool = Field(...)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")

