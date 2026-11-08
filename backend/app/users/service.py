import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_service import revoke_user_tokens
from app.core.security import hash_password, verify_password
from app.db.filters import filter_active
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.users import AdminUserUpdate, UserUpdatePassword


def get_current_user_profile(user: User) -> User:
    """Returns the authenticated user profile."""
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    payload: UserUpdatePassword,
) -> User:
    """Validates old password and updates user's password with a newly hashed value."""
    if not verify_password(payload.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be identical to current password.",
        )

    user.hashed_password = hash_password(payload.new_password)
    user.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(user)
    return user


async def admin_list_users(
    db: AsyncSession,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[User]:
    """Lists users for administrators.

    By default, soft-deleted records are excluded.
    """
    stmt = select(User)
    if not include_deleted:
        stmt = filter_active(stmt, User)
    stmt = stmt.order_by(User.created_at.desc(), User.id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def admin_update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    update_data: AdminUserUpdate,
    actor_id: uuid.UUID | None = None,
) -> User:
    """Updates user status, role, or soft-delete state.

    If the user is deactivated or soft-deleted, active refresh tokens are revoked.
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    target_user = result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id '{user_id}' was not found.",
        )

    audit_meta: dict[str, str | bool | None] = {}
    should_revoke_tokens = False

    if update_data.role is not None:
        audit_meta["previous_role"] = (
            target_user.role.value if hasattr(target_user.role, "value") else str(target_user.role)
        )
        target_user.role = update_data.role
        audit_meta["new_role"] = (
            update_data.role.value if hasattr(update_data.role, "value") else str(update_data.role)
        )

    if update_data.is_active is not None:
        audit_meta["previous_is_active"] = target_user.is_active
        target_user.is_active = update_data.is_active
        audit_meta["new_is_active"] = update_data.is_active
        if not update_data.is_active:
            should_revoke_tokens = True

    if update_data.is_deleted is True:
        target_user.deleted_at = datetime.now(UTC)
        audit_meta["deleted_at"] = target_user.deleted_at.isoformat()
        should_revoke_tokens = True
    elif update_data.is_deleted is False:
        target_user.deleted_at = None
        audit_meta["deleted_at"] = None
    elif update_data.deleted_at is not None:
        target_user.deleted_at = update_data.deleted_at
        audit_meta["deleted_at"] = target_user.deleted_at.isoformat()
        should_revoke_tokens = True

    if should_revoke_tokens:
        await revoke_user_tokens(db, target_user.id)

    target_user.updated_at = datetime.now(UTC)

    # Record audit log entry
    audit_entry = AuditLog(
        actor_id=actor_id,
        action="ADMIN_UPDATE_USER",
        entity_type="User",
        entity_id=target_user.id,
        metadata_json=audit_meta,
    )
    db.add(audit_entry)

    await db.commit()
    await db.refresh(target_user)
    return target_user
