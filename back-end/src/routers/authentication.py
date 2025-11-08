from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from orjson import loads, dumps
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

# from jwcrypto import jwk, jwt as jwc_jwt

from models.relational_models import User
from schemas.relational_schemas import RelationalUserPublic
from schemas.user import UserCreate
from utilities.authentication import get_password_hash, refresh_header_scheme
from dependencies import _verify_cnf_simple, get_session
from utilities.authentication import authenticate_user, create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES
from utilities.enumerables import UserRole


router = APIRouter()

@router.post(
    "/sign-up/",
    response_model=RelationalUserPublic,
)
async def create_user(
        *,
        session: AsyncSession = Depends(get_session),
        user_create: UserCreate,
):
    if user_create.role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(
            status_code=403,
            detail="بیا 👍"
        )
    
    hashed_password = get_password_hash(user_create.password)

    try:
        db_user = User(
            full_name=user_create.username,
            email=user_create.email,
            phone=user_create.phone,
            username=user_create.username,
            role=user_create.role,
            account_status=user_create.account_status,
            password=hashed_password,
        )

        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)

        return db_user

    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="نام کاربری یا پست الکترونیکی یا شماره تلفن قبلا ثبت شده است"
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد کاربر: "
        )

@router.post("/login/")
async def login(*,
        session: AsyncSession = Depends(get_session), 
        request: Request, 
        form: OAuth2PasswordRequestForm = Depends()
    ):
    client_jwk_b64 = request.headers.get("X-Client-JWK")
    client_jwk = None
    if client_jwk_b64:
        try:
            client_jwk_json = loads(
                bytes.fromhex(client_jwk_b64).decode()
            )
            client_jwk = client_jwk_json
        except Exception:
            raise HTTPException(status_code=400, detail="فرمت JWK ناقص است")
    
    user = await authenticate_user(form, session)

    user_id = str(user["user_id"])
    role = user["user_role"]
    full_name = user["user_full_name"]
    status = user["user_account_status"]

    access_payload = {"sub": user_id, "role": role, "token_type": "access", "jti": "access-" + user_id + "-" + str(int(datetime.now(timezone.utc).timestamp()))}
    refresh_payload = {"sub": user_id, "role": role, "token_type": "refresh", "jti": "refresh-" + user_id + "-" + str(int(datetime.now(timezone.utc).timestamp()))}

    if client_jwk:
        refresh_payload["cnf"] = {"jwk": client_jwk}
        access_payload["cnf"] = {"jwk": client_jwk}

    access_token = create_access_token(access_payload, ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token = create_access_token(refresh_payload, REFRESH_TOKEN_EXPIRE_MINUTES)

    return {
        "user_id": user_id,
        "user_role": role,
        "user_full_name": full_name,
        "user_status": status,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "access_expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_expires_in": REFRESH_TOKEN_EXPIRE_MINUTES * 60
    }


# ------------------------------------------------------------------
# Refresh token endpoint (simplified, single header-based check)
# ------------------------------------------------------------------

# NOTE: The router decorator is given here as an example. In your project
# the router may already exist and the endpoint should be placed accordingly.

@router.post("/refresh-token/")
async def refresh_token(
    request: Request,
    refresh_header: str | None = Depends(refresh_header_scheme)
):
    """
    Refresh access and refresh tokens.

    Behavior:
      - Accepts the refresh token either in the custom refresh header or in
        the standard Authorization header (Bearer).
      - If the token's payload contains `cnf.jwk`, the client must send the
        same JWK in X-Client-JWK header (simple equality check).
      - Generates new access and refresh JWTs (calls create_access_token which
        should be implemented elsewhere).
    """
    token = None
    if refresh_header:
        token = refresh_header.removeprefix("Bearer").strip()

    if not token:
        header_auth = request.headers.get("Authorization")
        if header_auth:
            token = header_auth.removeprefix("Bearer").strip()

    if not token:
        raise HTTPException(status_code=401, detail="No refresh or access token found (header/cookie/query).")

    # DPoP removed — use simple cnf header verification if necessary
    payload = decode_access_token(token, verify_exp=True)

    token_type = payload.get("token_type")
    if token_type not in ("access", "refresh"):
        raise HTTPException(status_code=401, detail="Unsupported token type")

    # If cnf.jwk present, enforce header equality check
    cnf = payload.get("cnf")
    if cnf and "jwk" in cnf:
        client_jwk_json = cnf["jwk"]
        _verify_cnf_simple(request, client_jwk_json)

    user_id = payload.get("sub")
    user_role = payload.get("role")

    now_ts = str(int(datetime.now(timezone.utc).timestamp()))
    new_access_payload = {
        "sub": user_id,
        "role": user_role,
        "token_type": "access",
        "jti": f"access-{now_ts}"
    }
    new_refresh_payload = {
        "sub": user_id,
        "role": user_role,
        "token_type": "refresh",
        "jti": f"refresh-{now_ts}"
    }

    if payload.get("cnf"):
        new_access_payload["cnf"] = payload["cnf"]
        new_refresh_payload["cnf"] = payload["cnf"]

    new_access = create_access_token(new_access_payload, ACCESS_TOKEN_EXPIRE_MINUTES)
    new_refresh = create_access_token(new_refresh_payload, REFRESH_TOKEN_EXPIRE_MINUTES)

    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}
