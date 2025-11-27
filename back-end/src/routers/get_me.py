from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dependencies import get_current_user, get_session, require_roles
from models.relational_models import User
from schemas.relational_schemas import RelationalUserPublic
from utilities.authentication import oauth2_scheme
from utilities.enumerables import UserRole


router = APIRouter()

@router.get(
    "/get_me/",
    response_model=RelationalUserPublic
)
async def get_me(
    *,
    session: AsyncSession = Depends(get_session),
    _user: dict = Depends(
        # Only FULL_ADMIN and ADMIN can create blogs
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.JOB_SEEKER.value,
            UserRole.EMPLOYER.value
        )
    ),
    _: str = Depends(oauth2_scheme),
    current_user: dict = Depends(get_current_user)
):
    """
    Return the currently authenticated user's details.

    - Uses the get_current_user dependency to obtain the authenticated user's identity.
    - Uses an async DB session (get_session) to fetch the full User record from the database.
    - No request body or query parameters are required; the request must be authenticated.
    """
    user_id = current_user.get("id")

    if user_id is None:
        # This should not normally happen because get_current_user enforces authentication,
        # but defend against a missing id just in case.
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Convert numeric-string IDs to int when appropriate. If your User.id is UUID,
    # remove this conversion or replace with UUID(...) conversion as needed.
    try:
        user_pk = int(user_id)
    except Exception:
        user_pk = user_id
    
    # Query the database for the User row matching the authenticated user's id.
    # Assumes a SQLModel model named `User` with a primary key `id`.
    stmt = select(User).where(User.id == user_pk)
    result = await session.exec(stmt)
    db_user = result.one_or_none()  # returns None if no match found

    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Return the database user object — FastAPI will convert it to the UserRead schema.
    return db_user
