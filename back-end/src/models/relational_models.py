from datetime import datetime
from uuid import uuid4, UUID

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func
from schemas.base.employer_company import CompanyBase
from schemas.base.image import ImageBase
from schemas.base.job_application import JobApplicationBase
from schemas.base.job_posting import JobPostingBase
from schemas.base.job_seeker_education import JobSeekerEducationBase
from schemas.base.job_seeker_personal_information import JobSeekerPersonalInformationBase
from schemas.base.job_seeker_resume import JobSeekerResumeBase
from schemas.base.job_seeker_skill import JobSeekerSkillBase
from schemas.base.job_seeker_work_experience import JobSeekerWorkExperienceBase
from schemas.base.notification import NotificationBase
from schemas.base.saved_job import SavedJobBase
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

    companies: list["Company"] = Relationship(
        back_populates="user",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    images: list["Image"] = Relationship(
        back_populates="user",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    notifications: list["Notification"] = Relationship(
        back_populates="user",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    saved_jobs: list["SavedJob"] = Relationship(
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

    job_applications: list["JobApplication"] = Relationship(
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


class Company(DefaultFields, CompanyBase, table=True):
    user: User = Relationship(
        back_populates="companies",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_postings: list["JobPosting"] = Relationship(
        back_populates="company",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class Image(DefaultFields, ImageBase, table=True):
    user: User = Relationship(
        back_populates="images",
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class JobPosting(DefaultFields, JobPostingBase, table=True):
    job_applications: list["JobApplication"] = Relationship(
        back_populates="job_posting",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    company: Company = Relationship(
        back_populates="job_postings",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    saved_jobs: list["SavedJob"] = Relationship(
        back_populates="job_posting",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class JobApplication(DefaultFields, JobApplicationBase, table=True):
    job_posting: JobPosting = Relationship(
        back_populates="job_applications",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    resume: JobSeekerResume = Relationship(
        back_populates="job_applications",
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class Notification(DefaultFields, NotificationBase, table=True):
    user: User = Relationship(
        back_populates="notifications",
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class SavedJob(DefaultFields, SavedJobBase, table=True):
    user: User = Relationship(
        back_populates="saved_jobs",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_posting: JobPosting = Relationship(
        back_populates="saved_jobs",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
