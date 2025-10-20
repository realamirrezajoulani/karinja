from uuid import UUID
from sqlmodel import Field, SQLModel

from utilities.enumerables import JobSeekerCertificateVerificationStatus, JobSeekerProficiencyLevel


class JobSeekerSkillBase(SQLModel):
    # min_length=5, max_length=30
    title: str = Field(index=True)

    # min_length=5, max_length=30
    proficiency_level: JobSeekerProficiencyLevel = Field(index=True)

    has_certificate: bool = Field(...)

    # min_length=5, max_length=30
    certificate_issuing_organization: str | None = Field(
        default=None,
        index=True
    )

    # min_length=5, max_length=30
    certificate_code: str | None = Field(default=None)

    certificate_verification_status: JobSeekerCertificateVerificationStatus | None = Field(
        default=None
    )
