import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_token
from app.models.user import RefreshToken, User


class InvalidRefreshTokenError(Exception):
    """Raised when a refresh token cannot be rotated."""


async def revoke_user_tokens(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Sets revoked=True on all active refresh tokens for the given user."""
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
        .values(revoked=True)
    )
    result = await db.execute(stmt)
    return int(result.rowcount)


async def create_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    expires_delta: timedelta | None = None,
) -> tuple[str, RefreshToken]:
    """Generates and persists a new refresh token for a user."""
    raw_token = secrets.token_urlsafe(48)
    token_digest = hash_token(raw_token)
    expires_at = datetime.now(UTC) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )

    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_digest,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(refresh_token)
    await db.flush()
    return raw_token, refresh_token


async def get_valid_refresh_token(
    db: AsyncSession,
    raw_token: str,
) -> RefreshToken | None:
    """Retrieves a refresh token if it exists, is not revoked, and is unexpired."""
    token_digest = hash_token(raw_token)
    now = datetime.now(UTC)

    stmt = select(RefreshToken).where(
        RefreshToken.token_hash == token_digest,
        RefreshToken.revoked.is_(False),
        RefreshToken.expires_at > now,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_refresh_token(
    db: AsyncSession,
    raw_token: str,
    *,
    include_revoked: bool = False,
    for_update: bool = False,
) -> RefreshToken | None:
    """Looks up a refresh token by its SHA-256 digest.

    When ``for_update`` is true, the row is locked for the duration of the current
    transaction, which serializes concurrent refreshes of the same token.
    """
    token_digest = hash_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_digest)
    if not include_revoked:
        stmt = stmt.where(RefreshToken.revoked.is_(False))
    if for_update:
        stmt = stmt.with_for_update()

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> bool:
    """Revokes a single refresh token by its raw value. Returns whether a row changed."""
    token_digest = hash_token(raw_token)
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == token_digest,
            RefreshToken.revoked.is_(False),
        )
        .values(revoked=True)
    )
    result = await db.execute(stmt)
    return bool(result.rowcount)


async def rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
) -> tuple[str, RefreshToken, User]:
    """Validates and rotates a refresh token under a row-level lock.

    The old token is marked revoked and a new token is flushed, but the caller is
    responsible for committing the transaction. Raises ``InvalidRefreshTokenError``
    for missing, revoked, expired, or inactive-owner tokens.
    """
    token = await get_refresh_token(db, raw_token, for_update=True)
    if token is None:
        raise InvalidRefreshTokenError

    if token.expires_at <= datetime.now(UTC):
        raise InvalidRefreshTokenError

    user = await db.get(User, token.user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise InvalidRefreshTokenError

    token.revoked = True
    new_raw_token, new_token = await create_refresh_token(db, user.id)
    return new_raw_token, new_token, user
