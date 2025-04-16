from datetime import datetime
from uuid import uuid4, UUID

from sqlmodel import Column, DateTime, Field, Relationship, func
from schemas.base.job_seeker_personal_information import JobSeekerPersonalInformationBase
from schemas.base.job_seeker_resume import JobSeekerResumeBase
from schemas.base.user import UserBase


class User(UserBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    password: str = Field(...)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )

    job_seeker_resumes: list["JobSeekerResume"] = Relationship(
        back_populates="user",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class JobSeekerPersonalInformation(JobSeekerPersonalInformationBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    job_seeker_resumes: list["JobSeekerResume"] = Relationship(
        back_populates="job_seeker_personal_information",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class JobSeekerResume(JobSeekerResumeBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user: User = Relationship(
        back_populates="job_seeker_resumes",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )

    job_seeker_personal_information: JobSeekerPersonalInformation = Relationship(
        back_populates="job_seeker_resumes",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
