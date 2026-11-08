import asyncio
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.token_service import (
    InvalidRefreshTokenError,
    create_refresh_token,
    get_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.core.config import settings
from app.core.security import hash_token
from app.models.user import User


@pytest.mark.asyncio
async def test_rotate_refresh_token_success(db_session, attendee_user: User) -> None:
    """Rotation revokes the old token, issues a new one, and returns the owner."""
    raw_old, old_token = await create_refresh_token(db_session, attendee_user.id)
    await db_session.commit()

    raw_new, new_token, user = await rotate_refresh_token(db_session, raw_old)
    await db_session.commit()

    assert user.id == attendee_user.id
    assert raw_new != raw_old
    assert old_token.revoked is True
    assert new_token.revoked is False
    assert new_token.token_hash == hash_token(raw_new)

    assert await get_refresh_token(db_session, raw_old) is None
    assert (await get_refresh_token(db_session, raw_old, include_revoked=True)) is not None
    assert await get_refresh_token(db_session, raw_new) is not None

    with pytest.raises(InvalidRefreshTokenError):
        await rotate_refresh_token(db_session, raw_old)
    await db_session.rollback()


@pytest.mark.asyncio
async def test_rotate_refresh_token_rejects_expired(
    db_session,
    attendee_user: User,
) -> None:
    """Expired refresh tokens cannot be rotated."""
    raw_token, _ = await create_refresh_token(
        db_session,
        attendee_user.id,
        expires_delta=timedelta(seconds=-1),
    )
    await db_session.commit()

    with pytest.raises(InvalidRefreshTokenError):
        await rotate_refresh_token(db_session, raw_token)
    await db_session.rollback()


@pytest.mark.asyncio
async def test_rotate_refresh_token_rejects_inactive_user(
    db_session,
    attendee_user: User,
) -> None:
    """Refresh tokens stop rotating when the owning user is inactive."""
    raw_token, _ = await create_refresh_token(db_session, attendee_user.id)
    await db_session.commit()

    attendee_user.is_active = False
    await db_session.commit()

    with pytest.raises(InvalidRefreshTokenError):
        await rotate_refresh_token(db_session, raw_token)
    await db_session.rollback()


@pytest.mark.asyncio
async def test_revoke_refresh_token_is_single_use(
    db_session,
    attendee_user: User,
) -> None:
    """revoke_refresh_token revokes only the matching token and is idempotent."""
    raw_a, _ = await create_refresh_token(db_session, attendee_user.id)
    raw_b, _ = await create_refresh_token(db_session, attendee_user.id)
    await db_session.commit()

    assert await revoke_refresh_token(db_session, raw_a) is True
    await db_session.commit()
    assert await revoke_refresh_token(db_session, raw_a) is False

    assert await get_refresh_token(db_session, raw_a) is None
    assert (await get_refresh_token(db_session, raw_a, include_revoked=True)) is not None
    assert await get_refresh_token(db_session, raw_b) is not None


@pytest.mark.asyncio
async def test_concurrent_rotation_allows_exactly_one_success(
    db_session,
    attendee_user: User,
) -> None:
    """Two concurrent rotations of the same token: exactly one succeeds."""
    raw_token, _ = await create_refresh_token(db_session, attendee_user.id)
    await db_session.commit()

    engine = create_async_engine(settings.ASYNC_DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    barrier = asyncio.Barrier(2)

    async def attempt() -> bool:
        async with session_factory() as session:
            await barrier.wait()
            try:
                await rotate_refresh_token(session, raw_token)
                await session.commit()
                return True
            except InvalidRefreshTokenError:
                await session.rollback()
                return False

    try:
        results = await asyncio.gather(attempt(), attempt())
    finally:
        await engine.dispose()

    assert results.count(True) == 1
    assert results.count(False) == 1
