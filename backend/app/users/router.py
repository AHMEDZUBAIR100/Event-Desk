import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, ownership_check, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.users import AdminUserUpdate, UserRead, UserUpdatePassword
from app.users import service

users_router = APIRouter(prefix="/users", tags=["Users"])
admin_users_router = APIRouter(
    prefix="/admin/users",
    tags=["Admin Users"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


@users_router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user profile",
    status_code=status.HTTP_200_OK,
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Returns the profile of the currently authenticated user."""
    return service.get_current_user_profile(current_user)


@users_router.patch(
    "/me",
    response_model=UserRead,
    summary="Change current user password",
    status_code=status.HTTP_200_OK,
)
async def update_my_password(
    payload: UserUpdatePassword,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Changes password for the currently authenticated user after verifying the current password."""
    ownership_check(current_user.id, current_user)
    return await service.change_password(db=db, user=current_user, payload=payload)


@admin_users_router.get(
    "",
    response_model=list[UserRead],
    summary="List all users (Admin only)",
    status_code=status.HTTP_200_OK,
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    include_deleted: Annotated[
        bool,
        Query(description="Whether to include soft-deleted users"),
    ] = False,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page limit"),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0, description="Offset for pagination"),
    ] = 0,
) -> list[User]:
    """Lists users in the platform.

    By default, soft-deleted accounts are excluded unless include_deleted=True.
    """
    return await service.admin_list_users(
        db=db,
        include_deleted=include_deleted,
        limit=limit,
        offset=offset,
    )


@admin_users_router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update user role, status or soft-delete (Admin only)",
    status_code=status.HTTP_200_OK,
)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    admin_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Updates user role, activation status, or soft-delete flag.

    Deactivation bulk-revokes all existing refresh tokens for that user.
    """
    return await service.admin_update_user(
        db=db,
        user_id=user_id,
        update_data=payload,
        actor_id=admin_user.id,
    )


# Combined router containing both /users and /admin/users
router = APIRouter()
router.include_router(users_router)
router.include_router(admin_users_router)
