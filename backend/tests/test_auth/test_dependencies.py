import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.core.config import settings
from app.models.user import User, UserRole


def create_token(user_id: uuid.UUID, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=15))
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


class DummyCredentials:
    def __init__(self, token: str):
        self.credentials = token


@pytest.mark.asyncio
async def test_get_current_user_valid(db_session: AsyncSession) -> None:
    """Tests successful user resolution from valid JWT."""
    user = User(
        email=f"auth_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Auth User",
        role=UserRole.ATTENDEE,
    )
    db_session.add(user)
    await db_session.flush()

    token = create_token(user.id)
    credentials = DummyCredentials(token)

    current_user = await get_current_user(credentials=credentials, db=db_session)
    assert current_user.id == user.id
    assert current_user.email == user.email


@pytest.mark.asyncio
async def test_get_current_user_expired_token(db_session: AsyncSession) -> None:
    """Tests that expired tokens raise 401 Unauthorized."""
    token = create_token(uuid.uuid4(), expires_delta=timedelta(minutes=-5))
    credentials = DummyCredentials(token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials, db=db_session)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_require_role_enforcement() -> None:
    """Tests that require_role raises 403 when the user does not possess the required role."""
    attendee = User(
        id=uuid.uuid4(),
        email="att@example.com",
        hashed_password="hash",
        full_name="Attendee",
        role=UserRole.ATTENDEE,
    )

    organizer_checker = require_role(UserRole.ORGANIZER, UserRole.ADMIN)

    # Calling with attendee must raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        organizer_checker(current_user=attendee)
    assert exc_info.value.status_code == 403

    # Calling with organizer must succeed
    organizer = User(
        id=uuid.uuid4(),
        email="org@example.com",
        hashed_password="hash",
        full_name="Organizer",
        role=UserRole.ORGANIZER,
    )
    result = organizer_checker(current_user=organizer)
    assert result.role == UserRole.ORGANIZER
