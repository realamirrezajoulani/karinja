from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from routers import main


description = """
A lightweight RESTful API for a karinja application using FastAPI and SQLModel 🚀
"""


app = FastAPI(title="karinja API",
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


app.include_router(main.router, tags=["main"])
