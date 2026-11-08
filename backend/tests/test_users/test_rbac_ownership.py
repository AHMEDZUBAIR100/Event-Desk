import uuid

import pytest
from fastapi import HTTPException

from app.auth.dependencies import ownership_check, require_role
from app.models.user import User, UserRole


def test_ownership_check_same_user_succeeds() -> None:
    """Verifies ownership_check passes when resource_user_id matches current_user.id."""
    user_id = uuid.uuid4()
    user = User(id=user_id, role=UserRole.ATTENDEE)
    # Should not raise
    ownership_check(resource_user_id=user_id, current_user=user)


def test_ownership_check_different_user_raises_403() -> None:
    """Verifies ownership_check raises 403 when resource_user_id does not match."""
    user = User(id=uuid.uuid4(), role=UserRole.ATTENDEE)
    diff_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        ownership_check(resource_user_id=diff_id, current_user=user)
    assert exc_info.value.status_code == 403
    assert "forbidden" in exc_info.value.detail.lower()


def test_ownership_check_admin_override() -> None:
    """Verifies ownership_check with allow_admin=True passes for admin and fails for non-admin."""
    admin = User(id=uuid.uuid4(), role=UserRole.ADMIN)
    organizer = User(id=uuid.uuid4(), role=UserRole.ORGANIZER)
    other_id = uuid.uuid4()

    # Admin passes when allow_admin=True
    ownership_check(resource_user_id=other_id, current_user=admin, allow_admin=True)

    # Admin fails when allow_admin=False
    with pytest.raises(HTTPException) as exc_info:
        ownership_check(resource_user_id=other_id, current_user=admin, allow_admin=False)
    assert exc_info.value.status_code == 403

    # Organizer fails even with allow_admin=True
    with pytest.raises(HTTPException) as exc_info:
        ownership_check(resource_user_id=other_id, current_user=organizer, allow_admin=True)
    assert exc_info.value.status_code == 403


def test_require_role_with_enum_and_strings() -> None:
    """Verifies require_role supports both UserRole enum values and strings."""
    admin = User(id=uuid.uuid4(), role=UserRole.ADMIN)
    organizer = User(id=uuid.uuid4(), role=UserRole.ORGANIZER)
    attendee = User(id=uuid.uuid4(), role=UserRole.ATTENDEE)

    admin_checker = require_role(UserRole.ADMIN)
    assert admin_checker(current_user=admin) == admin

    with pytest.raises(HTTPException) as exc_1:
        admin_checker(current_user=organizer)
    assert exc_1.value.status_code == 403

    # String-based definition
    org_or_admin_checker = require_role("organizer", "admin")
    assert org_or_admin_checker(current_user=admin) == admin
    assert org_or_admin_checker(current_user=organizer) == organizer

    with pytest.raises(HTTPException) as exc_2:
        org_or_admin_checker(current_user=attendee)
    assert exc_2.value.status_code == 403
