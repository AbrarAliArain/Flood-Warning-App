"""Request and response models for the auth API."""
from pydantic import BaseModel, Field

from ..core import security


class UserResponse(BaseModel):
    id: int
    full_name: str
    phone: str | None = None
    email: str | None = None
    role: str
    ngo_id: int | None = None
    ngo_name: str | None = None
    is_active: bool
    is_demo: bool
    created_at: str


class RegisterRequest(BaseModel):
    """Public self-registration. Always creates a CITIZEN account — responder
    and admin accounts are provisioned by an admin so that nobody can grant
    themselves dispatch authority."""

    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=200)
    phone: str | None = Field(None, max_length=32)
    email: str | None = Field(None, max_length=200)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=200, description="Phone number or email")
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse


class UpdateMeRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=120)
    phone: str | None = Field(None, max_length=32)
    email: str | None = Field(None, max_length=200)


class AdminCreateUserRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=200)
    phone: str | None = Field(None, max_length=32)
    email: str | None = Field(None, max_length=200)
    role: str = Field(security.CITIZEN, pattern=f"^({'|'.join(sorted(security.ROLES))})$")
    ngo_id: int | None = None


class AdminUpdateUserRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=120)
    phone: str | None = Field(None, max_length=32)
    email: str | None = Field(None, max_length=200)
    role: str | None = Field(None, pattern=f"^({'|'.join(sorted(security.ROLES))})$")
    ngo_id: int | None = None
    is_active: bool | None = None
