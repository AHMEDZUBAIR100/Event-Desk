from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.users import UserRead


class RegisterRequest(BaseModel):
    """Payload for public self-registration."""

    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password (8-128 characters)",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Display name",
    )
    role: UserRole = UserRole.ATTENDEE


class LoginRequest(BaseModel):
    """Payload for credential-based login."""

    email: EmailStr
    password: str = Field(
        ...,
        min_length=1,
        description="Plaintext password",
    )


class RefreshRequest(BaseModel):
    """Payload for refreshing an access token."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Opaque refresh token issued at login or on the previous refresh",
    )


class LogoutRequest(BaseModel):
    """Payload for revoking the current refresh token."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Opaque refresh token to revoke",
    )


class TokenPair(BaseModel):
    """Access/refresh token pair returned by the API."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        ...,
        description="Access-token lifetime in seconds",
    )


class AuthResponse(TokenPair):
    """Token pair plus the authenticated user's public profile."""

    user: UserRead
