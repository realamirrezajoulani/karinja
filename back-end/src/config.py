from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import lifespan
from routers import api_status, job_seeker_personal_information, job_seeker_resume, user, job_seeker_education, job_seeker_skill, job_seeker_work_experience, employer_company, authentication, activity_log, job_application, saved_job, image, notification, job_posting



description = """
A lightweight RESTful API for a karinja application using FastAPI and SQLModel 🚀
"""


app = FastAPI(lifespan=lifespan,
              title="karinja API",
              description=description,
              version="0.0.1",
              contact={
                  "name": "Amirreza Joulani",
                  "email": "realamirrezajoulani@gmail.com",
              },
              license_info={
                  "name": "MIT",
                  "url": "https://opensource.org/license/MIT",
              },
              default_response_class=ORJSONResponse)

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=4)


origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://localhost:5000",
    "https://localhost:5000"
    "http://localhost:5173",
    "https://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "OPTIONS", "HEAD", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "accept", "Authorization", "Authorization-Refresh", "X-Client-JWK", "DPoP"],
)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Expect-CT"] = "max-age=86400, enforce"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["X-Frame-Options"] = "DENY"
    return response


app.include_router(api_status.router, tags=["API status"])
app.include_router(authentication.router, tags=["Authentication"])
app.include_router(user.router, tags=["Users"])
app.include_router(job_seeker_resume.router, tags=["Job Seeker Resumes"])
app.include_router(job_seeker_personal_information.router, tags=["Job Seeker Personal Informations"])
app.include_router(job_seeker_education.router, tags=["Job Seeker Education"])
app.include_router(job_seeker_skill.router, tags=["Job Seeker Skill"])
app.include_router(job_seeker_work_experience.router, tags=["Job Seeker Work Experiences"])
app.include_router(employer_company.router, tags=["Employer Company"])



app.include_router(activity_log.router, tags=["Activity Log"])
app.include_router(job_application.router, tags=["Job Application"])
app.include_router(saved_job.router, tags=["Saved Job"])
app.include_router(image.router, tags=["Image"])
app.include_router(notification.router, tags=["Notification"])
app.include_router(job_posting.router, tags=["Job Posting"])