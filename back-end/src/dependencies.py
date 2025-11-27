from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Callable, Dict
from orjson import dumps, loads

from fastapi import HTTPException, Request, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from database import async_engine
from utilities.authentication import decode_access_token
from jwcrypto import jwk, jwt as jwc_jwt


# ------------------------------------------------------------------
# Helper: extract client JWK from a simple header (hex-encoded JSON)
# ------------------------------------------------------------------

def _client_jwk_from_header(request: Request) -> dict | None:
    """
    Read the client JWK from the `X-Client-JWK` header.

    The header is expected to contain the JSON representation of the
    JWK encoded as hex (this preserves compatibility with the original
    implementation). If the header is missing, return None.

    If the header is present but malformed, raise HTTPException(400).

    Returns:
        dict | None: parsed JWK dict or None when header is missing.
    """
    client_jwk_b64 = request.headers.get("X-Client-JWK")
    if not client_jwk_b64:
        return None
    try:
        client_jwk_json = loads(bytes.fromhex(client_jwk_b64).decode())
        return client_jwk_json
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JWK format in X-Client-JWK header")


# ------------------------------------------------------------------
# Helper: simple verification of cnf.jwk against header-provided JWK
# ------------------------------------------------------------------

def _verify_cnf_simple(request: Request, cnf_jwk: Dict[str, Any]) -> None:
    """
    Simple verification for a token-bound client key (cnf.jwk).

    This function enforces a very small and easy-to-understand rule:
    if the access/refresh token contains `cnf.jwk`, then the client must
    send the exact same JWK in the `X-Client-JWK` header. If the header is
    missing or does not match, a 401 is raised.

    NOTE: This is intentionally simple and does NOT prove possession of
    the private key. It only checks that the client provides the same
    JWK object that the token binds to. Do NOT consider this a secure
    replacement for PoP/DPoP or mTLS in production.
    """
    header_jwk = _client_jwk_from_header(request)
    if header_jwk is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client JWK required in X-Client-JWK header.")

    # simple dict equality check; if you prefer a thumbprint or another
    # normalization step, replace this comparison accordingly
    if header_jwk != cnf_jwk:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provided JWK does not match cnf.jwk in token.")


# ------------------------------------------------------------------
# Dependency: get_current_user (simplified, cnf uses header check)
# ------------------------------------------------------------------

async def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Extract and validate the access token from the Authorization header.

    - Decodes the JWT with `decode_access_token` (function assumed present
      elsewhere in your codebase) which raises HTTPException on invalid/expired tokens.
    - Ensures token_type == 'access'.
    - Ensures required claims (sub/id and role) exist.
    - If the token contains `cnf.jwk`, enforce that the client sent the
      same JWK in the X-Client-JWK header (simple equality check).

    Returns a dictionary describing the current user (id, role, and other
    non-duplicate claims).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = auth_header.removeprefix("Bearer").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No token provided")

    # decode_access_token should be defined elsewhere and raise HTTPException on problems
    try:
        payload = decode_access_token(token)
    except HTTPException:
        raise
    except Exception:
        # hide internal errors from clients
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")

    token_type = payload.get("token_type")
    if token_type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Provided token is not an access token")

    user_id = payload.get("sub") or payload.get("id")
    role = payload.get("role")
    if not user_id or not role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token claims are incomplete")

    # If the token is bound to a client key (cnf.jwk) -> verify via header
    cnf = payload.get("cnf")
    if cnf:
        jwk_in_cnf = cnf.get("jwk") if isinstance(cnf, dict) else None
        if not jwk_in_cnf:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has invalid cnf claim")
        _verify_cnf_simple(request, jwk_in_cnf)

    # Return a minimal user dict; avoid exposing raw token fields named id/sub/role
    return {"id": user_id, "role": role, **{k: v for k, v in payload.items() if k not in ("id", "sub", "role")}}


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
