from datetime import datetime
from uuid import uuid4, UUID

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func
from schemas.base.job_seeker_education import JobSeekerEducationBase
from schemas.base.job_seeker_personal_information import JobSeekerPersonalInformationBase
from schemas.base.job_seeker_resume import JobSeekerResumeBase
from schemas.base.job_seeker_skill import JobSeekerSkillBase
from schemas.base.job_seeker_work_experience import JobSeekerWorkExperienceBase
from schemas.base.user import UserBase


class DefaultFields(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )

    class Config:
        table = False


class User(DefaultFields, UserBase, table=True):
    password: str = Field(...)

    job_seeker_resumes: list["JobSeekerResume"] = Relationship(
        back_populates="user",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class JobSeekerPersonalInformation(DefaultFields, JobSeekerPersonalInformationBase, table=True):
    job_seeker_resumes: list["JobSeekerResume"] = Relationship(
        back_populates="job_seeker_personal_information",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class JobSeekerResume(DefaultFields, JobSeekerResumeBase, table=True):
    user: User = Relationship(
        back_populates="job_seeker_resumes",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_seeker_personal_information: JobSeekerPersonalInformation = Relationship(
        back_populates="job_seeker_resumes",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_seeker_skills: list["JobSeekerSkill"] = Relationship(
        back_populates="resume",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_seeker_work_experiences: list["JobSeekerWorkExperience"] = Relationship(
        back_populates="resume",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_seeker_educations: list["JobSeekerEducation"] = Relationship(
        back_populates="resume",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class JobSeekerSkill(DefaultFields, JobSeekerSkillBase, table=True):
    resume: JobSeekerResume = Relationship(
        back_populates="job_seeker_skills",
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class JobSeekerWorkExperience(DefaultFields, JobSeekerWorkExperienceBase, table=True):
    resume: JobSeekerResume = Relationship(
        back_populates="job_seeker_work_experiences",
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class JobSeekerEducation(DefaultFields, JobSeekerEducationBase, table=True):
    resume: JobSeekerResume = Relationship(
        back_populates="job_seeker_educations",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
