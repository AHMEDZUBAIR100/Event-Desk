import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserRead(BaseModel):
    """Public/API user representation schema."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserUpdatePassword(BaseModel):
    """Schema for authenticated user password change."""

    old_password: str = Field(
        ...,
        min_length=1,
        description="Current plaintext password",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="New plaintext password (minimum 8 characters)",
    )


class AdminUserUpdate(BaseModel):
    """Schema for administrator updates to user accounts."""

    role: UserRole | None = None
    is_active: bool | None = None
    deleted_at: datetime | None = None
    is_deleted: bool | None = None

    model_config = ConfigDict(extra="ignore")
