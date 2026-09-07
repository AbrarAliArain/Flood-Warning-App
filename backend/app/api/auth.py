"""Auth API: registration, login, profile and admin user management."""
from fastapi import APIRouter, Depends, HTTPException

from ..auth import service
from ..auth.deps import admin_user, current_user
from ..auth.schemas import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserResponse,
)
from ..core import config, security
from ..core.logging_conf import get_logger

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = get_logger(__name__)


def _issue(user: dict) -> TokenResponse:
    return TokenResponse(
        access_token=security.create_access_token(
            user["id"], user["role"], user.get("ngo_name")
        ),
        expires_in_minutes=config.JWT_EXPIRES_MINUTES,
        user=UserResponse(**user),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest):
    """Create a CITIZEN account and return a session token."""
    try:
        user = service.create_user(
            full_name=body.full_name,
            password=body.password,
            role=security.CITIZEN,
            phone=body.phone,
            email=body.email,
        )
    except service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    log.info("citizen self-registered id=%s", user["id"])
    return _issue(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    try:
        user = service.authenticate(body.identifier, body.password)
    except service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _issue(user)


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(body: UpdateMeRequest, user: dict = Depends(current_user)):
    patch = body.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(status_code=422, detail="no fields to update")
    try:
        return service.update_user(user["id"], **patch)
    except service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/roles")
def roles():
    """Role catalogue the UI uses to label accounts."""
    return {
        "roles": [
            {
                "id": security.CITIZEN,
                "label": "Citizen",
                "description": "Report flooding, request rescue, track own cases.",
            },
            {
                "id": security.RESPONDER,
                "label": "Responder / NGO",
                "description": "Receive assigned emergency cases and update rescue status.",
            },
            {
                "id": security.ADMIN,
                "label": "Administrator",
                "description": "Manage users, NGOs, risk data and system configuration.",
            },
        ]
    }


@router.get("/users", response_model=list[UserResponse])
def list_users(role: str | None = None, _: dict = Depends(admin_user)):
    return service.list_users(role=role)


@router.post("/users", response_model=TokenResponse, status_code=201)
def admin_create_user(body: AdminCreateUserRequest, _: dict = Depends(admin_user)):
    """Provision a responder or admin account (admin only)."""
    try:
        user = service.create_user(
            full_name=body.full_name,
            password=body.password,
            role=body.role,
            phone=body.phone,
            email=body.email,
            ngo_id=body.ngo_id,
        )
    except service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    log.info("admin provisioned %s account id=%s", body.role, user["id"])
    return _issue(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def admin_update_user(
    user_id: int, body: AdminUpdateUserRequest, _: dict = Depends(admin_user)
):
    patch = body.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(status_code=422, detail="no fields to update")
    try:
        return service.update_user(user_id, **patch)
    except service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/stats")
def stats(_: dict = Depends(admin_user)):
    return {"users_by_role": service.count_by_role()}
