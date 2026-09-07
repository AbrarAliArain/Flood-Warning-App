"""FastAPI dependencies for authentication and role-based authorisation."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core import security
from . import service

bearer = HTTPBearer(
    auto_error=False, description="JWT issued by POST /api/auth/login"
)

UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)


def _resolve(credentials: HTTPAuthorizationCredentials | None) -> dict | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    payload = security.decode_token(credentials.credentials)
    if payload is None:
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
    return service.find_by_id(user_id)


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict | None:
    """Attach the caller when a valid token is present, otherwise None.

    Used by endpoints that stay publicly readable but personalise their
    response for a signed-in citizen.
    """
    return _resolve(credentials)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    user = _resolve(credentials)
    if user is None:
        raise UNAUTHENTICATED
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="this account is deactivated")
    return user


def require_role(*roles: str):
    """Build a dependency that admits only the given roles."""
    allowed = set(roles)
    if not allowed:
        raise ValueError("require_role needs at least one role")

    def dependency(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"requires role: {' or '.join(sorted(allowed))}",
            )
        return user

    return dependency


staff_user = require_role(security.RESPONDER, security.ADMIN)
admin_user = require_role(security.ADMIN)
