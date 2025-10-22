from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Callable, Dict
from orjson import dumps, loads

from fastapi import HTTPException, Request, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from database import async_engine
from utilities.authentication import decode_access_token
from jwcrypto import jwk, jwt as jwc_jwt


def _validate_dpop_proof(request: Request, cnf_jwk: Dict[str, Any]) -> None:
    """
    Validate a DPoP proof JWT carried in header "DPoP" against the client's public JWK
    supplied inside token 'cnf.jwk'. This is a basic set of checks:
      - signature verification using the provided JWK
      - presence of htm, htu, iat, jti claims
      - http method match (htm)
      - htu endswith request.path (basic path-check)
      - iat close to now (e.g. within ±300s)
    Raises HTTPException(401) on any failure.
    """
    dpop = request.headers.get("DPoP")
    if not dpop:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DPoP proof required")

    # load JWK (expect dict-like)
    try:
        jwk_json = dumps(cnf_jwk)
        jwk_obj = jwk.JWK.from_json(jwk_json)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="کلید مشتری نامعتبر است")

    # verify signature & parse claims
    try:
        # jwcrypto.jwt.JWT will verify signature
        dpop_jwt = jwc_jwt.JWT(jwt=dpop, key=jwk_obj)
        dpop_claims = loads(dpop_jwt.claims)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DPoP proof امضا/فرمت نامعتبر است")

    # required claims
    htm = dpop_claims.get("htm")
    htu = dpop_claims.get("htu")
    iat = dpop_claims.get("iat")
    jti = dpop_claims.get("jti")

    if not (htm and htu and iat and jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DPoP proof ناقص است")

    # method must match
    if htm.upper() != request.method.upper():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DPoP proof با متد درخواست همخوانی ندارد")

    # basic htu check: ensure path matches (allowing full URL or path)
    # e.g. client may set htu to origin+path or just path; we do a suffix check for robustness
    req_path = request.url.path
    if not htu.endswith(req_path):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DPoP proof با مسیر درخواست همخوانی ندارد")

    # iat time window (prevent replay with old proofs) -- permit small clock skew
    try:
        iat_ts = int(iat)
    except Exception:
        # sometimes iat might be float/string; try convert
        try:
            iat_ts = int(float(iat))
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DPoP proof iat نامعتبر است")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    max_skew = 300  # seconds
    if abs(now_ts - iat_ts) > max_skew:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DPoP proof منقضی یا دارای اختلاف زمانی است")

    # jti present (can be logged/monitored for anomalies)
    # NOTE: since you are stateless, we cannot store jti server-side to enforce single-use.
    return


# ----- Dependency: get_current_user -----
async def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Extract and validate access token from Authorization header.
    Returns the token payload as a dict (must include 'sub' and 'role').
    If payload contains 'cnf' with a 'jwk', validates the DPoP proof in header "DPoP".
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="احراز هویت نشده است")

    token = auth_header.removeprefix("Bearer").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="توکن ارسال‌شده معتبر نیست")

    # decode_access_token should raise HTTPException on invalid/expired token.
    try:
        payload = decode_access_token(token)
    except HTTPException:
        raise  # passthrough (already appropriate status/detail)
    except Exception:
        # fallback: do not reveal internal errors
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="احراز هویت ناموفق بود")

    # minimal required claims
    token_type = payload.get("token_type")
    if token_type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="توکن ارسالی توکن دسترسی نیست")

    user_id = payload.get("sub") or payload.get("id")  # support either claim name
    role = payload.get("role")
    if not user_id or not role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ادعاهای توکن ناقص است")

    # If token is bound to client key -> enforce DPoP proof
    cnf = payload.get("cnf")
    if cnf:
        jwk_in_cnf = cnf.get("jwk") if isinstance(cnf, dict) else None
        if not jwk_in_cnf:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="توکن دارای cnf نامعتبر است")
        _validate_dpop_proof(request, jwk_in_cnf)

    # you may want to return a lighter object (e.g. {"id": user_id, "role": role})
    # to avoid exposing full token claims to downstream handlers.
    return {"id": user_id, "role": role, **{k: v for k, v in payload.items() if k not in ("id","sub","role")}}
    # note: we keep full payload except duplicate id/sub/role but primary keys returned explicitly


# ----- Dependency factory: require_roles -----
def require_roles(*required_roles: str) -> Callable[..., Dict[str, Any]]:
    """
    Usage:
        @router.get("/admin")
        async def admin_route(user = Depends(require_roles("admin"))):
            ...
    If no roles passed, defaults to allowing any authenticated user.
    """
    def dependency(_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        # if no role restriction specified -> permit any authenticated user
        if not required_roles:
            return _user

        user_role = _user.get("role")
        if user_role not in required_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="شما دسترسی لازم را ندارید")
        return _user

    return dependency


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Asynchronous dependency to provide a database session.

    This function creates and manages an asynchronous database session using SQLAlchemy's AsyncSession.
    It ensures proper session handling, including cleanup after use.

    Yields:
        AsyncSession: A database session that can be used for queries.

    Example:
        async with get_session() as session:
            result = await session.execute(statement)
            data = result.scalars().all()

    Raises:
        Exception: If session creation fails (unlikely, but can be handled for logging).
    """
    async with AsyncSession(async_engine) as session:
        yield session  # Provide the session to the caller
