import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_service import create_refresh_token
from app.core.security import hash_password, hash_token, verify_password
from app.models.user import RefreshToken, User, UserRole


def _unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


async def _delete_users(db: AsyncSession, emails: list[str]) -> None:
    normalized = [email.lower() for email in emails]
    await db.execute(delete(User).where(func.lower(User.email).in_(normalized)))
    await db.commit()


def _login_payload(email: str, password: str) -> dict[str, str]:
    return {"email": email, "password": password}


async def _login(client: AsyncClient, email: str, password: str) -> dict[str, object]:
    response = await client.post("/api/v1/auth/login", json=_login_payload(email, password))
    assert response.status_code == 200
    return response.json()


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.mark.asyncio
async def test_register_attendee_and_organizer(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Registers both self-service roles and verifies password hashing."""
    emails: list[str] = []
    try:
        for role in (UserRole.ATTENDEE, UserRole.ORGANIZER):
            email = _unique_email(f"register_{role.value}")
            emails.append(email)
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "password": "StrongPass123!",
                    "full_name": f"New {role.value}",
                    "role": role.value,
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["email"] == email
            assert data["full_name"] == f"New {role.value}"
            assert data["role"] == role.value
            assert data["is_active"] is True
            assert "hashed_password" not in data
            assert "password" not in data

            stored = (
                await db_session.execute(select(User).where(User.email == email))
            ).scalar_one()
            assert stored.hashed_password != "StrongPass123!"
            assert verify_password("StrongPass123!", stored.hashed_password)
    finally:
        await _delete_users(db_session, emails)


@pytest.mark.asyncio
async def test_register_defaults_to_attendee(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Omitting role registers an attendee."""
    email = _unique_email("default_role")
    try:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "StrongPass123!",
                "full_name": "Default Role",
            },
        )
        assert response.status_code == 201
        assert response.json()["role"] == UserRole.ATTENDEE.value
    finally:
        await _delete_users(db_session, [email])


@pytest.mark.asyncio
async def test_register_admin_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Admin self-registration is forbidden and inserts no row."""
    email = _unique_email("admin_self")
    try:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "StrongPass123!",
                "full_name": "Wannabe Admin",
                "role": UserRole.ADMIN.value,
            },
        )
        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()

        stored = (
            await db_session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        assert stored is None
    finally:
        await _delete_users(db_session, [email])


@pytest.mark.asyncio
async def test_register_duplicate_active_email_conflict(
    client: AsyncClient,
    attendee_user: User,
) -> None:
    """An active email cannot be registered twice."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": attendee_user.email,
            "password": "AnotherPass123!",
            "full_name": "Duplicate",
        },
    )
    assert response.status_code == 409
    assert "exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_allows_soft_deleted_email_reuse(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A soft-deleted account's email may be reused by a new active account."""
    email = _unique_email("reuse_deleted")
    deleted_user = User(
        email=email,
        hashed_password=hash_password("OldPass123!"),
        full_name="Deleted User",
        role=UserRole.ATTENDEE,
        deleted_at=datetime.now(UTC),
    )
    db_session.add(deleted_user)
    await db_session.commit()

    try:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "StrongPass123!",
                "full_name": "Replacement User",
            },
        )
        assert response.status_code == 201
        assert response.json()["email"] == email

        active_rows = (
            (
                await db_session.execute(
                    select(User).where(
                        func.lower(User.email) == email,
                        User.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(active_rows) == 1
    finally:
        await _delete_users(db_session, [email])


@pytest.mark.parametrize(
    "payload",
    [
        {
            "email": "short-pass@example.com",
            "password": "short",
            "full_name": "Short Password",
        },
        {
            "email": "not-an-email",
            "password": "StrongPass123!",
            "full_name": "Bad Email",
        },
        {
            "email": "blank-name@example.com",
            "password": "StrongPass123!",
            "full_name": "",
        },
    ],
)
@pytest.mark.asyncio
async def test_register_validation(client: AsyncClient, payload: dict[str, str]) -> None:
    """Invalid registration payloads fail Pydantic validation."""
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success_and_access_token(
    client: AsyncClient,
    db_session: AsyncSession,
    attendee_user: User,
) -> None:
    """Login returns a token pair, a user profile, and stores only the refresh hash."""
    data = await _login(client, attendee_user.email, attendee_user.raw_password)  # type: ignore[attr-defined]

    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["id"] == str(attendee_user.id)
    assert "hashed_password" not in data["user"]

    me_response = await client.get(
        "/api/v1/users/me",
        headers=_auth_headers(str(data["access_token"])),
    )
    assert me_response.status_code == 200
    assert me_response.json()["id"] == str(attendee_user.id)

    token_row = (
        await db_session.execute(
            select(RefreshToken).where(RefreshToken.user_id == attendee_user.id)
        )
    ).scalar_one()
    assert token_row.token_hash == hash_token(str(data["refresh_token"]))
    assert token_row.token_hash != data["refresh_token"]


@pytest.mark.asyncio
async def test_login_email_is_case_insensitive(
    client: AsyncClient,
    attendee_user: User,
) -> None:
    """Login normalizes the email before lookup."""
    data = await _login(
        client,
        attendee_user.email.upper(),
        attendee_user.raw_password,  # type: ignore[attr-defined]
    )
    assert data["user"]["id"] == str(attendee_user.id)


@pytest.mark.asyncio
async def test_login_invalid_credentials_are_generic(
    client: AsyncClient,
    db_session: AsyncSession,
    attendee_user: User,
    deactivated_user: User,
) -> None:
    """Wrong password, unknown email, inactive, and deleted users return the same 401."""
    soft_deleted_email = _unique_email("deleted_login")
    soft_deleted_user = User(
        email=soft_deleted_email,
        hashed_password=hash_password("StrongPass123!"),
        full_name="Deleted Login",
        role=UserRole.ATTENDEE,
        deleted_at=datetime.now(UTC),
    )
    db_session.add(soft_deleted_user)
    await db_session.commit()

    attempts = [
        (attendee_user.email, "WrongPassword999!"),
        (_unique_email("missing_user"), "StrongPass123!"),
        (deactivated_user.email, deactivated_user.raw_password),  # type: ignore[attr-defined]
        (soft_deleted_email, "StrongPass123!"),
    ]

    try:
        for email, password in attempts:
            response = await client.post(
                "/api/v1/auth/login",
                json=_login_payload(email, password),
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid email or password."
    finally:
        await _delete_users(db_session, [soft_deleted_email])


@pytest.mark.asyncio
async def test_refresh_rotates_and_rejects_reuse(
    client: AsyncClient,
    attendee_user: User,
) -> None:
    """A refresh token rotates once; the old token can never be reused."""
    login_data = await _login(
        client,
        attendee_user.email,
        attendee_user.raw_password,  # type: ignore[attr-defined]
    )
    old_refresh = str(login_data["refresh_token"])

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response.status_code == 200
    rotated = response.json()
    assert rotated["refresh_token"] != old_refresh
    assert rotated["access_token"]
    assert rotated["user"]["id"] == str(attendee_user.id)

    reuse_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert reuse_response.status_code == 401

    second_rotation = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rotated["refresh_token"]},
    )
    assert second_rotation.status_code == 200


@pytest.mark.asyncio
async def test_refresh_rejects_malformed_and_expired_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
    attendee_user: User,
) -> None:
    """Malformed and expired refresh tokens are rejected."""
    user_id = attendee_user.id
    malformed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not-a-real-token"},
    )
    assert malformed.status_code == 401

    expired_raw, _ = await create_refresh_token(
        db_session,
        user_id,
        expires_delta=timedelta(seconds=-1),
    )
    await db_session.commit()

    expired = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": expired_raw},
    )
    assert expired.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_and_deleted_users(
    client: AsyncClient,
    db_session: AsyncSession,
    attendee_user: User,
    organizer_user: User,
) -> None:
    """Issued refresh tokens stop working when the owner is deactivated or deleted."""
    inactive_raw, _ = await create_refresh_token(db_session, attendee_user.id)
    deleted_raw, _ = await create_refresh_token(db_session, organizer_user.id)
    await db_session.commit()

    attendee_user.is_active = False
    organizer_user.deleted_at = datetime.now(UTC)
    await db_session.commit()

    inactive_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": inactive_raw},
    )
    assert inactive_response.status_code == 401

    deleted_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": deleted_raw},
    )
    assert deleted_response.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_and_is_idempotent(
    client: AsyncClient,
    attendee_user: User,
) -> None:
    """Logout revokes the presented refresh token and can be repeated safely."""
    login_data = await _login(
        client,
        attendee_user.email,
        attendee_user.raw_password,  # type: ignore[attr-defined]
    )
    headers = _auth_headers(str(login_data["access_token"]))
    refresh_token = str(login_data["refresh_token"])

    logout = await client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": refresh_token},
    )
    assert logout.status_code == 204
    assert logout.content == b""

    refresh_after_logout = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_after_logout.status_code == 401

    repeated_logout = await client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": refresh_token},
    )
    assert repeated_logout.status_code == 204


@pytest.mark.asyncio
async def test_logout_does_not_revoke_another_users_token(
    client: AsyncClient,
    attendee_user: User,
    organizer_user: User,
) -> None:
    """A user cannot revoke a refresh token owned by someone else."""
    attendee_login = await _login(
        client,
        attendee_user.email,
        attendee_user.raw_password,  # type: ignore[attr-defined]
    )
    organizer_login = await _login(
        client,
        organizer_user.email,
        organizer_user.raw_password,  # type: ignore[attr-defined]
    )

    response = await client.post(
        "/api/v1/auth/logout",
        headers=_auth_headers(str(organizer_login["access_token"])),
        json={"refresh_token": attendee_login["refresh_token"]},
    )
    assert response.status_code == 204

    still_valid = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": attendee_login["refresh_token"]},
    )
    assert still_valid.status_code == 200


@pytest.mark.asyncio
async def test_logout_requires_authentication(client: AsyncClient) -> None:
    """Logout without a bearer token returns 401."""
    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "anything"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_full_auth_flow(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """register -> login -> authenticated request -> refresh -> logout -> refresh fails."""
    email = _unique_email("full_flow")
    try:
        register = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "StrongPass123!",
                "full_name": "Full Flow",
            },
        )
        assert register.status_code == 201

        login_data = await _login(client, email, "StrongPass123!")
        access_token = str(login_data["access_token"])
        first_refresh = str(login_data["refresh_token"])

        me = await client.get("/api/v1/users/me", headers=_auth_headers(access_token))
        assert me.status_code == 200
        assert me.json()["email"] == email

        rotated = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": first_refresh},
        )
        assert rotated.status_code == 200
        second_refresh = str(rotated.json()["refresh_token"])
        second_access = str(rotated.json()["access_token"])

        logout = await client.post(
            "/api/v1/auth/logout",
            headers=_auth_headers(second_access),
            json={"refresh_token": second_refresh},
        )
        assert logout.status_code == 204

        refresh_after_logout = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": second_refresh},
        )
        assert refresh_after_logout.status_code == 401
    finally:
        await _delete_users(db_session, [email])
