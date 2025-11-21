from datetime import datetime
from uuid import uuid4, UUID

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, Text, func
from schemas.base.activity_log import ActivityLogBase
from schemas.base.blog import BlogBase
from schemas.base.comment import CommentBase
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
from schemas.base.setting import SettingBase
from schemas.base.ticket import TicketBase
from schemas.base.user import UserBase


class User(UserBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    password: str = Field(...)

    job_seeker_resumes: list["JobSeekerResume"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    companies: list["Company"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    images: list["Image"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    notifications: list["Notification"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    saved_jobs: list["SavedJob"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    activity_logs: list["ActivityLog"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    blogs: list["Blog"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    writed_comments: list["Comment"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    tickets: list["Ticket"] = Relationship(
        back_populates="requester_user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    settings: list["Setting"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class JobSeekerPersonalInformation(JobSeekerPersonalInformationBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    job_seeker_resume_id: UUID = Field(foreign_key="jobseekerresume.id", ondelete="CASCADE")
    job_seeker_resume: "JobSeekerResume" = Relationship(
        back_populates="job_seeker_personal_information",
        sa_relationship_kwargs={"lazy": "selectin", "uselist": False}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class JobSeekerResume(JobSeekerResumeBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    user: User = Relationship(
        back_populates="job_seeker_resumes",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_seeker_personal_information: JobSeekerPersonalInformation | None = Relationship(
        back_populates="job_seeker_resume",
        sa_relationship_kwargs={"lazy": "selectin", "uselist": False}
    )

    job_seeker_skills: list["JobSeekerSkill"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_seeker_work_experiences: list["JobSeekerWorkExperience"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_seeker_educations: list["JobSeekerEducation"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_applications: list["JobApplication"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class JobSeekerSkill(JobSeekerSkillBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    job_seeker_resume_id: UUID = Field(foreign_key="jobseekerresume.id", ondelete="CASCADE")
    resume: JobSeekerResume = Relationship(
        back_populates="job_seeker_skills",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class JobSeekerWorkExperience(JobSeekerWorkExperienceBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    job_seeker_resume_id: UUID = Field(foreign_key="jobseekerresume.id", ondelete="CASCADE")
    resume: JobSeekerResume = Relationship(
        back_populates="job_seeker_work_experiences",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class JobSeekerEducation(JobSeekerEducationBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    job_seeker_resume_id: UUID = Field(foreign_key="jobseekerresume.id", ondelete="CASCADE")
    resume: JobSeekerResume = Relationship(
        back_populates="job_seeker_educations",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class Company(CompanyBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    user: User = Relationship(
        back_populates="companies",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_postings: list["JobPosting"] = Relationship(
        back_populates="company",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class Image(ImageBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    user: User = Relationship(
        back_populates="images",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class JobPosting(JobPostingBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    job_applications: list["JobApplication"] = Relationship(
        back_populates="job_posting",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    company_id: UUID = Field(foreign_key="company.id", ondelete="CASCADE")
    company: Company = Relationship(
        back_populates="job_postings",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    saved_jobs: list["SavedJob"] = Relationship(
        back_populates="job_posting",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class JobApplication(JobApplicationBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    job_posting_id: UUID = Field(foreign_key="jobposting.id", ondelete="CASCADE")
    job_posting: JobPosting = Relationship(
        back_populates="job_applications",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_seeker_resume_id: UUID = Field(foreign_key="jobseekerresume.id", ondelete="CASCADE")
    resume: JobSeekerResume = Relationship(
        back_populates="job_applications",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class Notification(NotificationBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    user: User = Relationship(
        back_populates="notifications",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class SavedJob(SavedJobBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    user: User = Relationship(
        back_populates="saved_jobs",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    job_posting_id: UUID = Field(foreign_key="jobposting.id", ondelete="CASCADE")
    job_posting: JobPosting = Relationship(
        back_populates="saved_jobs",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class ActivityLog(ActivityLogBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    user: User = Relationship(
        back_populates="activity_logs",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class Blog(BlogBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="user.id", index=True)
    user: User = Relationship(
        back_populates="blogs",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    comments: list["Comment"] = Relationship(
        back_populates="blog",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class Comment(CommentBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    blog_id: UUID = Field(foreign_key="blog.id", index=True)
    blog: Blog = Relationship(
        back_populates="comments",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    user_id: UUID = Field(foreign_key="user.id", index=True)
    user: User = Relationship(
        back_populates="writed_comments",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class Ticket(TicketBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    requester_user_id: UUID = Field(foreign_key="user.id", index=True)
    requester_user: User = Relationship(
        back_populates="tickets",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class Setting(SettingBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="user.id", index=True)
    user: User = Relationship(
        back_populates="settings",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )