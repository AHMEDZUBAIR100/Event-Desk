import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_admin_list_users_rbac_matrix(
    client: AsyncClient,
    admin_user: User,
    organizer_user: User,
    attendee_user: User,
    deactivated_user: User,
) -> None:
    """Verifies RBAC rules for GET /admin/users:

    - Admin: 200 OK
    - Organizer: 403 Forbidden
    - Attendee: 403 Forbidden
    - Deactivated: 401 Unauthorized
    """
    # Admin succeeds
    resp_admin = await client.get("/api/v1/admin/users", headers=admin_user.headers)  # type: ignore[attr-defined]
    assert resp_admin.status_code == 200
    users = resp_admin.json()
    assert isinstance(users, list)
    assert len(users) >= 3

    # Organizer fails (403)
    resp_org = await client.get("/api/v1/admin/users", headers=organizer_user.headers)  # type: ignore[attr-defined]
    assert resp_org.status_code == 403

    # Attendee fails (403)
    resp_att = await client.get("/api/v1/admin/users", headers=attendee_user.headers)  # type: ignore[attr-defined]
    assert resp_att.status_code == 403

    # Deactivated fails (401)
    resp_deact = await client.get(
        "/api/v1/admin/users",
        headers=deactivated_user.headers,  # type: ignore[attr-defined]
    )
    assert resp_deact.status_code == 401


@pytest.mark.asyncio
async def test_admin_list_users_soft_delete_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
) -> None:
    """Verifies that soft-deleted users are excluded by default and included only when requested."""
    # Create an active user and a soft-deleted user
    suffix = uuid.uuid4().hex[:8]
    soft_deleted_user = User(
        email=f"soft_del_{suffix}@example.com",
        hashed_password="hash",
        full_name=f"Soft Deleted {suffix}",
        role=UserRole.ATTENDEE,
        deleted_at=datetime.now(UTC),
    )
    db_session.add(soft_deleted_user)
    await db_session.commit()
    await db_session.refresh(soft_deleted_user)

    try:
        # Default query (include_deleted=False) must NOT contain soft-deleted user
        resp_default = await client.get(
            "/api/v1/admin/users",
            headers=admin_user.headers,  # type: ignore[attr-defined]
        )
        assert resp_default.status_code == 200
        user_ids_default = [u["id"] for u in resp_default.json()]
        assert str(soft_deleted_user.id) not in user_ids_default

        # Query with include_deleted=True MUST contain soft-deleted user
        resp_with_deleted = await client.get(
            "/api/v1/admin/users?include_deleted=true",
            headers=admin_user.headers,  # type: ignore[attr-defined]
        )
        assert resp_with_deleted.status_code == 200
        items = resp_with_deleted.json()
        matching = [u for u in items if u["id"] == str(soft_deleted_user.id)]
        assert len(matching) == 1
        assert matching[0]["deleted_at"] is not None
    finally:
        await db_session.delete(soft_deleted_user)
        await db_session.commit()


@pytest.mark.asyncio
async def test_admin_list_users_pagination(
    client: AsyncClient,
    admin_user: User,
    organizer_user: User,
    attendee_user: User,
) -> None:
    """Verifies limit/offset pagination and ordering for GET /admin/users."""
    resp_page_1 = await client.get(
        "/api/v1/admin/users?limit=1&offset=0",
        headers=admin_user.headers,  # type: ignore[attr-defined]
    )
    assert resp_page_1.status_code == 200
    assert len(resp_page_1.json()) == 1

    resp_page_2 = await client.get(
        "/api/v1/admin/users?limit=1&offset=1",
        headers=admin_user.headers,  # type: ignore[attr-defined]
    )
    assert resp_page_2.status_code == 200
    page_1_ids = [u["id"] for u in resp_page_1.json()]
    page_2_ids = [u["id"] for u in resp_page_2.json()]
    assert page_1_ids != page_2_ids

    # Invalid bounds are rejected by validation.
    resp_invalid = await client.get(
        "/api/v1/admin/users?limit=0",
        headers=admin_user.headers,  # type: ignore[attr-defined]
    )
    assert resp_invalid.status_code == 422


@pytest.mark.asyncio
async def test_admin_patch_user_rbac_matrix(
    client: AsyncClient,
    admin_user: User,
    organizer_user: User,
    attendee_user: User,
    deactivated_user: User,
) -> None:
    """Verifies RBAC rules for PATCH /admin/users/{id}:

    - Admin: 200 OK
    - Organizer: 403 Forbidden
    - Attendee: 403 Forbidden
    - Deactivated: 401 Unauthorized
    """
    target_id = str(attendee_user.id)
    payload = {"role": UserRole.ORGANIZER.value}

    # Organizer forbidden
    resp_org = await client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert resp_org.status_code == 403

    # Attendee forbidden
    resp_att = await client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=attendee_user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert resp_att.status_code == 403

    # Deactivated unauthorized
    resp_deact = await client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=deactivated_user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert resp_deact.status_code == 401

    # Admin succeeds
    resp_admin = await client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json()["role"] == UserRole.ORGANIZER.value


@pytest.mark.asyncio
async def test_admin_patch_user_deactivation_and_soft_delete(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    attendee_user: User,
) -> None:
    """Verifies that an admin can deactivate, soft-delete, restore, and that audit logs are recorded."""
    target_id = str(attendee_user.id)

    # 1. Deactivate
    resp_deact = await client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"is_active": False},
    )
    assert resp_deact.status_code == 200
    assert resp_deact.json()["is_active"] is False

    # 2. Soft-delete
    resp_del = await client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"is_deleted": True},
    )
    assert resp_del.status_code == 200
    assert resp_del.json()["deleted_at"] is not None

    # 3. Restore soft-delete
    resp_restore = await client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"is_deleted": False, "is_active": True},
    )
    assert resp_restore.status_code == 200
    assert resp_restore.json()["deleted_at"] is None
    assert resp_restore.json()["is_active"] is True

    # 4. Check audit log was inserted
    audit_stmt = select(AuditLog).where(
        AuditLog.entity_id == attendee_user.id,
        AuditLog.action == "ADMIN_UPDATE_USER",
    )
    audit_entries = (await db_session.execute(audit_stmt)).scalars().all()
    assert len(audit_entries) >= 3
    assert all(entry.actor_id == admin_user.id for entry in audit_entries)


@pytest.mark.asyncio
async def test_admin_patch_nonexistent_user(
    client: AsyncClient,
    admin_user: User,
) -> None:
    """Verifies 404 when updating non-existent user."""
    fake_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/admin/users/{fake_id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"is_active": False},
    )
    assert response.status_code == 404
