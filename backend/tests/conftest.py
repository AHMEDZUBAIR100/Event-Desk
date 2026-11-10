import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.event import Event
from app.models.user import User, UserRole


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated async database session with NullPool."""
    engine = create_async_engine(
        settings.ASYNC_DATABASE_URL,
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async test client using ASGI transport with get_db overridden to db_session."""

    async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


async def _create_test_user_record(
    db: AsyncSession,
    role: UserRole,
    is_active: bool = True,
    deleted_at: datetime | None = None,
) -> User:
    raw_password = "TestPassword123!"
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"test_{role.value}_{suffix}@example.com",
        hashed_password=hash_password(raw_password),
        full_name=f"Test {role.value.capitalize()} {suffix}",
        role=role,
        is_active=is_active,
        deleted_at=deleted_at,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    # Dynamically bind convenient testing attributes
    user.token = token  # type: ignore[attr-defined]
    user.headers = {"Authorization": f"Bearer {token}"}  # type: ignore[attr-defined]
    user.raw_password = raw_password  # type: ignore[attr-defined]
    return user


async def _delete_user_and_owned_events(db: AsyncSession, user_id: object) -> None:
    """Delete a test user's events first (FK is RESTRICT), then the user."""
    await db.execute(delete(Event).where(Event.organizer_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """Yields a persisted Admin user with active authentication tokens."""
    user = await _create_test_user_record(db_session, role=UserRole.ADMIN)
    user_id = user.id
    try:
        yield user
    finally:
        await _delete_user_and_owned_events(db_session, user_id)


@pytest.fixture
async def organizer_user(db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """Yields a persisted Organizer user with active authentication tokens."""
    user = await _create_test_user_record(db_session, role=UserRole.ORGANIZER)
    user_id = user.id
    try:
        yield user
    finally:
        await _delete_user_and_owned_events(db_session, user_id)


@pytest.fixture
async def attendee_user(db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """Yields a persisted Attendee user with active authentication tokens."""
    user = await _create_test_user_record(db_session, role=UserRole.ATTENDEE)
    user_id = user.id
    try:
        yield user
    finally:
        await db_session.execute(delete(User).where(User.id == user_id))
        await db_session.commit()


@pytest.fixture
async def deactivated_user(db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """Yields a deactivated user (is_active=False)."""
    user = await _create_test_user_record(
        db_session,
        role=UserRole.ATTENDEE,
        is_active=False,
    )
    user_id = user.id
    try:
        yield user
    finally:
        await db_session.execute(delete(User).where(User.id == user_id))
        await db_session.commit()
