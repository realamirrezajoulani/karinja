from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware

from database import lifespan
from routers import api_status, user



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
    "https://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "OPTIONS", "HEAD", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "accept", "Authorization", "Authorization-Refresh"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Expect-CT"] = "max-age=86400, enforce"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["X-Frame-Options"] = "DENY"
    return response


app.include_router(api_status.router, tags=["API status"])
app.include_router(user.router, tags=["Users"])

