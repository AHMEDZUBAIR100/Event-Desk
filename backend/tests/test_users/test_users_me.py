from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.models.user import User


@pytest.mark.asyncio
async def test_get_users_me_success_all_roles(
    client: AsyncClient,
    admin_user: User,
    organizer_user: User,
    attendee_user: User,
) -> None:
    """Verifies that admin, organizer, and attendee can all retrieve their own profile."""
    for user in (admin_user, organizer_user, attendee_user):
        response = await client.get(
            "/api/v1/users/me",
            headers=user.headers,  # type: ignore[attr-defined]
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(user.id)
        assert data["email"] == user.email
        assert data["full_name"] == user.full_name
        assert data["role"] == user.role.value
        assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_users_me_deactivated_fails(
    client: AsyncClient,
    deactivated_user: User,
) -> None:
    """Verifies that deactivated users cannot retrieve their profile (returns 401)."""
    response = await client.get(
        "/api/v1/users/me",
        headers=deactivated_user.headers,  # type: ignore[attr-defined]
    )
    assert response.status_code == 401
    assert "deactivated" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_users_me_unauthenticated_and_invalid_tokens(
    client: AsyncClient,
    attendee_user: User,
) -> None:
    """Verifies 401 unauthorized when tokens are missing, expired, or corrupted."""
    # Missing credentials
    resp_no_token = await client.get("/api/v1/users/me")
    assert resp_no_token.status_code == 401

    # Malformed token
    resp_bad = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid_or_corrupt_jwt"},
    )
    assert resp_bad.status_code == 401

    # Expired token
    expired_token = create_access_token(attendee_user.id, expires_delta=timedelta(minutes=-10))
    resp_expired = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp_expired.status_code == 401
    assert "expired" in resp_expired.json()["detail"].lower()


@pytest.mark.asyncio
async def test_patch_users_me_password_success(
    client: AsyncClient,
    db_session: AsyncSession,
    attendee_user: User,
) -> None:
    """Verifies successful password update via PATCH /users/me."""
    new_password = "BrandNewSecurePassword123!"

    payload = {
        "old_password": attendee_user.raw_password,  # type: ignore[attr-defined]
        "new_password": new_password,
    }
    response = await client.patch(
        "/api/v1/users/me",
        headers=attendee_user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(attendee_user.id)

    # Refresh user from database to verify hashed password update
    await db_session.refresh(attendee_user)
    assert verify_password(new_password, attendee_user.hashed_password)
    assert not verify_password(
        attendee_user.raw_password,  # type: ignore[attr-defined]
        attendee_user.hashed_password,
    )


@pytest.mark.asyncio
async def test_patch_users_me_password_success_admin_and_organizer(
    client: AsyncClient,
    admin_user: User,
    organizer_user: User,
) -> None:
    """Verifies the RBAC matrix: admin and organizer can change their own password too."""
    for index, user in enumerate((admin_user, organizer_user)):
        new_password = f"BrandNewSecurePassword{index}!"
        response = await client.patch(
            "/api/v1/users/me",
            headers=user.headers,  # type: ignore[attr-defined]
            json={
                "old_password": user.raw_password,  # type: ignore[attr-defined]
                "new_password": new_password,
            },
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(user.id)


@pytest.mark.asyncio
async def test_patch_users_me_incorrect_old_password(
    client: AsyncClient,
    attendee_user: User,
) -> None:
    """Verifies that an incorrect old password returns 400 Bad Request."""
    payload = {
        "old_password": "WrongPassword999!",
        "new_password": "ValidNewPassword123!",
    }
    response = await client.patch(
        "/api/v1/users/me",
        headers=attendee_user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert response.status_code == 400
    assert "incorrect" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_patch_users_me_same_password_rejected(
    client: AsyncClient,
    attendee_user: User,
) -> None:
    """Verifies that attempting to set the new password identical to the old password fails."""
    payload = {
        "old_password": attendee_user.raw_password,  # type: ignore[attr-defined]
        "new_password": attendee_user.raw_password,  # type: ignore[attr-defined]
    }
    response = await client.patch(
        "/api/v1/users/me",
        headers=attendee_user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert response.status_code == 400
    assert "identical" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_patch_users_me_password_too_short(
    client: AsyncClient,
    attendee_user: User,
) -> None:
    """Verifies that passwords shorter than 8 characters fail validation with 422."""
    payload = {
        "old_password": attendee_user.raw_password,  # type: ignore[attr-defined]
        "new_password": "short",
    }
    response = await client.patch(
        "/api/v1/users/me",
        headers=attendee_user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_users_me_deactivated_fails(
    client: AsyncClient,
    deactivated_user: User,
) -> None:
    """Verifies that deactivated users cannot change their password (returns 401)."""
    payload = {
        "old_password": deactivated_user.raw_password,  # type: ignore[attr-defined]
        "new_password": "NewSecretPassword123!",
    }
    response = await client.patch(
        "/api/v1/users/me",
        headers=deactivated_user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert response.status_code == 401
