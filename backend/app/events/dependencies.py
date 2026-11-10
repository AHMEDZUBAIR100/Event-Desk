import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, ownership_check
from app.db.session import get_db
from app.events import service
from app.models.event import Event
from app.models.user import User


async def get_managed_event(
    event_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    """Load an event under a row lock and enforce admin-any / organizer-own access.

    Raises 404 for missing or soft-deleted events and 403 when the caller is
    neither an admin nor the event's organizer (IDOR protection).
    """
    event = await service.get_event_with_lock(db, event_id)
    ownership_check(event.organizer_id, current_user, allow_admin=True)
    return event
