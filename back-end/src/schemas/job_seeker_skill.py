from datetime import datetime
from uuid import UUID
from sqlmodel import Field, SQLModel
from schemas.base.job_seeker_skill import JobSeekerSkillBase
from utilities.enumerables import JobSeekerCertificateVerificationStatus, JobSeekerProficiencyLevel


class JobSeekerSkillPublic(JobSeekerSkillBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class JobSeekerSkillCreate(JobSeekerSkillBase):
    pass


class JobSeekerSkillUpdate(SQLModel):
    # min_length=5, max_length=30
    title: str | None = Field(default=None)

    # min_length=5, max_length=30
    proficiency_level: JobSeekerProficiencyLevel | None = Field(default=None)

    has_certificate: bool | None = Field(default=None)

    # min_length=5, max_length=30
    certificate_issuing_organization: str | None = Field(default=None)

    # min_length=5, max_length=30
    certificate_code: str | None = Field(default=None)

    certificate_verification_status: JobSeekerCertificateVerificationStatus | None = Field(
        default=None
    )

