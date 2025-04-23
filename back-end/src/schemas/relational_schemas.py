from schemas.activity_log import ActivityLogPublic
from schemas.employer_company import CompanyPublic
from schemas.image import ImagePublic
from schemas.job_application import JobApplicationPublic
from schemas.job_posting import JobPostingPublic
from schemas.job_seeker_education import JobSeekerEducationPublic
from schemas.job_seeker_personal_information import JobSeekerPersonalInformationPublic
from schemas.job_seeker_resume import JobSeekerResumePublic
from schemas.job_seeker_skill import JobSeekerSkillPublic
from schemas.job_seeker_work_experience import JobSeekerWorkExperiencePublic
from schemas.notification import NotificationPublic
from schemas.saved_job import SavedJobPublic
from schemas.user import UserPublic


class RelationalUserPublic(UserPublic):
    job_seeker_resumes: list[JobSeekerResumePublic] = []
    companies: list[CompanyPublic] = []
    images: list[ImagePublic] = []
    notifications: list[NotificationPublic] = []
    saved_jobs: list[SavedJobPublic] = []
    activity_logs: list[ActivityLogPublic] = []


class RelationalJobSeekerPersonalInformationPublic(JobSeekerPersonalInformationPublic):
    job_seeker_resumes: list[JobSeekerResumePublic] = []


class RelationalJobSeekerResumePublic(JobSeekerResumePublic):
    user: UserPublic
    job_seeker_personal_information: JobSeekerPersonalInformationPublic
    job_seeker_skills: list[JobSeekerSkillPublic] = []
    job_seeker_work_experiences: list[JobSeekerWorkExperiencePublic] = []
    job_seeker_educations: list[JobSeekerEducationPublic] = []
    job_applications: list[JobApplicationPublic] = []


class RelationalJobSeekerSkillPublic(JobSeekerSkillPublic):
    resume: JobSeekerResumePublic


class RelationalJobSeekerWorkExperiencePublic(JobSeekerWorkExperiencePublic):
    resume: JobSeekerResumePublic


class RelationalJobSeekerEducationPublic(JobSeekerEducationPublic):
    resume: JobSeekerResumePublic


class RelationalCompanyPublic(CompanyPublic):
    user: UserPublic
    job_postings: list[JobPostingPublic] = []


class RelationalImagePublic(ImagePublic):
    user: UserPublic


class RelationalJobPostingPublic(JobPostingPublic):
    job_applications: list[JobApplicationPublic] = []
    company: CompanyPublic
    saved_jobs: list[SavedJobPublic] = []


class RelationalJobApplicationPublic(JobApplicationPublic):
    job_posting: JobPostingPublic
    resume: JobSeekerResumePublic


class RelationalNotificationPublic(NotificationPublic):
    user: UserPublic


class RelationalSavedJobPublic(SavedJobPublic):
    user: UserPublic
    job_posting: JobPostingPublic


class RelationalActivityLogPublic(ActivityLogPublic):
    user: UserPublic
