from fastapi import APIRouter


router = APIRouter()


@router.get("/main/")
async def main():
    return {"message": "Hello, World!"}
