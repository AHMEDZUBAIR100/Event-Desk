from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import token_service
from app.auth.token_service import InvalidRefreshTokenError
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, TokenPair
from app.schemas.users import UserRead

# Pre-computed hash used to keep failed logins for unknown emails roughly as slow
# as failed logins for known emails, reducing user-enumeration timing leaks.
_DUMMY_PASSWORD_HASH = hash_password("eventdesk-dummy-password")


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _auth_response(tokens: TokenPair, user: User) -> AuthResponse:
    return AuthResponse(
        **tokens.model_dump(),
        user=UserRead.model_validate(user),
    )


def _access_token_for(user: User) -> str:
    return create_access_token(
        user.id,
        extra_claims={"role": user.role.value, "type": "access"},
    )


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    """Registers a new attendee or organizer account."""
    if payload.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot be self-registered.",
        )

    normalized_email = str(payload.email).strip().lower()
    existing_stmt = select(User.id).where(
        func.lower(User.email) == normalized_email,
        User.deleted_at.is_(None),
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Verifies credentials and returns the active, non-deleted user."""
    normalized_email = email.strip().lower()
    stmt = select(User).where(
        func.lower(User.email) == normalized_email,
        User.deleted_at.is_(None),
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        # Perform a dummy verification so unknown emails are not distinguishable by timing.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        raise _invalid_credentials()

    if not verify_password(password, user.hashed_password):
        raise _invalid_credentials()

    if not user.is_active:
        raise _invalid_credentials()

    return user


async def issue_token_pair(db: AsyncSession, user: User) -> TokenPair:
    """Creates a refresh-token row and an access token for the user.

    The refresh token is flushed but not committed; callers own the transaction.
    """
    raw_refresh_token, _refresh_token = await token_service.create_refresh_token(db, user.id)
    return TokenPair(
        access_token=_access_token_for(user),
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def login(db: AsyncSession, payload: LoginRequest) -> AuthResponse:
    """Authenticates a user and returns a freshly issued token pair."""
    user = await authenticate_user(db, payload.email, payload.password)
    tokens = await issue_token_pair(db, user)
    response = _auth_response(tokens, user)
    await db.commit()
    return response


async def rotate_tokens(db: AsyncSession, raw_token: str) -> AuthResponse:
    """Rotates a refresh token and returns a new token pair."""
    try:
        new_refresh_token, _refresh_token, user = await token_service.rotate_refresh_token(
            db,
            raw_token,
        )
    except InvalidRefreshTokenError as exc:
        await db.rollback()
        raise _invalid_refresh_token() from exc

    tokens = TokenPair(
        access_token=_access_token_for(user),
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response = _auth_response(tokens, user)
    await db.commit()
    return response


async def logout(db: AsyncSession, user: User, raw_token: str) -> None:
    """Revokes the presented refresh token only when it belongs to the user."""
    token = await token_service.get_refresh_token(db, raw_token, include_revoked=True)

    if token is not None and token.user_id == user.id and not token.revoked:
        token.revoked = True
        await db.commit()
    else:
        # End the read transaction without changing anything.
        await db.rollback()
