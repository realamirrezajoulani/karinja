import os
from datetime import timedelta, timezone, datetime
from typing import Any

import jwt
from fastapi import HTTPException
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from schemas.authentication import LoginRequest
from models.relational_models import User

ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Access token lifetime (15 minutes)
REFRESH_TOKEN_EXPIRE_MINUTES = 10080  # Refresh token lifetime (7 days)

SECRET_KEY = os.getenv("P2_SECURITY_KEY")

ALGORITHM = "HS512"

# Password hashing context using PBKDF2-HMAC-SHA512
pwd_context = CryptContext(schemes=["pbkdf2_sha512"], deprecated="auto", pbkdf2_sha512__default_rounds=300_000)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/", )
refresh_header_scheme = APIKeyHeader(name="Authorization-Refresh", auto_error=False)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:

    # copy to avoid mutating the passed dict
    to_encode = data.copy()

    now = datetime.now(timezone.utc)

    # normalize expires_delta to a timedelta
    if isinstance(expires_delta, timedelta):
        delta = expires_delta
    elif isinstance(expires_delta, int):
        # interpret int as minutes
        delta = timedelta(minutes=expires_delta)
    elif expires_delta is None:
        delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        raise TypeError("expires_delta must be None, int (minutes), or timedelta")

    expire = now + delta

    # use an int timestamp for 'exp' to avoid any timezone/serialization edge cases
    to_encode.update({"exp": int(expire.timestamp())})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str, verify_exp: bool = True) -> dict:
    """
    Decode and verify a JWT. Raises HTTPException with a clear Persian message on error.
    """
    try:
        key = SECRET_KEY

        options = {"verify_exp": verify_exp}
        payload = jwt.decode(token, key, algorithms=[ALGORITHM], options=options)
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="توکن منقضی شده است")
    except jwt.InvalidSignatureError:
        raise HTTPException(status_code=401, detail="امضای توکن نامعتبر است")
    except jwt.InvalidAlgorithmError:
        raise HTTPException(status_code=401, detail="الگوریتم امضای توکن پشتیبانی نمی‌شود")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="فرمت/امضای توکن نامعتبر است")
    except Exception:
        raise HTTPException(status_code=401, detail="توکن نامعتبر است")


def get_password_hash(password: str) -> str:
    """
    Hashes the provided password using the bcrypt algorithm.

    Args:
        password (str): The plain password to be hashed.

    Returns:
        str: The hashed version of the provided password.

    This function hashes the provided password using the `hash` method from
    passlib's CryptContext. It's commonly used for securely storing passwords.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies whether the provided plain password matches the hashed password.

    Args:
        plain_password (str): The password in plain text to be verified.
        hashed_password (str): The hashed version of the password to compare against.

    Returns:
        bool: True if the plain password matches the hashed password, otherwise False.

    This function uses the `verify` method from passlib's CryptContext to compare
    the plain password with the stored hashed password. It handles exceptions gracefully
    and ensures the function always returns a boolean result.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except:
        # Log the exception or handle the error in a more meaningful way
        return False


async def authenticate_user(credentials: LoginRequest, session: AsyncSession):
    username, password = credentials.username, credentials.password

    result = await session.exec(select(User).where(User.username == username))

    user = result.one_or_none()

    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=401,
            detail="نام کاربری یا گذرواژه پیدا نشد"
        )
    
    return {"user_id": user.id, "user_role": user.role.value, "user_full_name": user.full_name, "user_account_status": user.account_status.value}
