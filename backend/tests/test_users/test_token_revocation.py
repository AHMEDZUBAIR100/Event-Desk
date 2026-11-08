from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_service import (
    create_refresh_token,
    get_valid_refresh_token,
    revoke_user_tokens,
)
from app.models.user import RefreshToken, User


@pytest.mark.asyncio
async def test_deactivation_bulk_revokes_refresh_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    attendee_user: User,
) -> None:
    """Verifies that admin deactivation of a user revokes all active refresh tokens for that user."""
    # 1. Create two active refresh tokens for attendee
    raw_token_1, _ = await create_refresh_token(db_session, attendee_user.id)
    raw_token_2, _ = await create_refresh_token(db_session, attendee_user.id)
    await db_session.commit()

    # Verify both are currently valid
    valid_1 = await get_valid_refresh_token(db_session, raw_token_1)
    valid_2 = await get_valid_refresh_token(db_session, raw_token_2)
    assert valid_1 is not None
    assert valid_2 is not None
    assert valid_1.revoked is False
    assert valid_2.revoked is False

    # 2. Admin deactivates the user via PATCH /admin/users/{user_id}
    resp = await client.patch(
        f"/api/v1/admin/users/{attendee_user.id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # 3. Check that both refresh tokens are now revoked in the database
    token_rows = (
        (
            await db_session.execute(
                select(RefreshToken).where(RefreshToken.user_id == attendee_user.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(token_rows) == 2
    assert all(t.revoked is True for t in token_rows)

    # 4. Attempting to get valid refresh token returns None
    assert await get_valid_refresh_token(db_session, raw_token_1) is None
    assert await get_valid_refresh_token(db_session, raw_token_2) is None

    # 5. Attempting to use existing access token must return 401 Unauthorized
    resp_access = await client.get(
        "/api/v1/users/me",
        headers=attendee_user.headers,  # type: ignore[attr-defined]
    )
    assert resp_access.status_code == 401


@pytest.mark.asyncio
async def test_soft_delete_revokes_refresh_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    organizer_user: User,
) -> None:
    """Verifies that soft-deleting a user also revokes their refresh tokens and blocks authentication."""
    raw_token, _ = await create_refresh_token(db_session, organizer_user.id)
    await db_session.commit()

    assert await get_valid_refresh_token(db_session, raw_token) is not None

    # Admin soft-deletes the organizer
    resp = await client.patch(
        f"/api/v1/admin/users/{organizer_user.id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"deleted_at": datetime.now(UTC).isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is not None

    # Token should be revoked
    assert await get_valid_refresh_token(db_session, raw_token) is None

    # Authentication with existing token fails with 401
    resp_auth = await client.get(
        "/api/v1/users/me",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
    )
    assert resp_auth.status_code == 401


@pytest.mark.asyncio
async def test_token_service_direct_revoke(
    db_session: AsyncSession,
    attendee_user: User,
) -> None:
    """Tests revoke_user_tokens service function directly."""
    _raw_token, _ = await create_refresh_token(db_session, attendee_user.id)
    await db_session.commit()

    count = await revoke_user_tokens(db_session, attendee_user.id)
    await db_session.commit()
    assert count >= 1

    # Additional call revokes 0 since already revoked
    count_2 = await revoke_user_tokens(db_session, attendee_user.id)
    assert count_2 == 0
