import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.session import get_db
from app.events import service
from app.events.dependencies import get_managed_event
from app.models.category import Category
from app.models.event import Event
from app.models.tag import Tag
from app.models.user import User, UserRole
from app.schemas.events import (
    CategoryCreate,
    CategoryRead,
    EventCreate,
    EventDetailRead,
    EventListResponse,
    EventRead,
    EventSortField,
    EventUpdate,
    SortOrder,
    TagCreate,
    TagRead,
)

router = APIRouter(tags=["Events"])

require_managed_roles = require_role(UserRole.ADMIN, UserRole.ORGANIZER)
require_admin = require_role(UserRole.ADMIN)


# ---------------------------------------------------------------------------
# Public catalogue
# ---------------------------------------------------------------------------


@router.get(
    "/events",
    response_model=EventListResponse,
    status_code=status.HTTP_200_OK,
    summary="List published events",
)
async def list_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    search: Annotated[
        str | None,
        Query(description="Case-insensitive title search"),
    ] = None,
    category: Annotated[str | None, Query(description="Category slug")] = None,
    tag: Annotated[
        list[str] | None,
        Query(description="Tag slug; repeatable with OR semantics"),
    ] = None,
    date_from: Annotated[
        datetime | None,
        Query(description="Only events starting at or after this instant"),
    ] = None,
    date_to: Annotated[
        datetime | None,
        Query(description="Only events starting at or before this instant"),
    ] = None,
    price_min: Annotated[Decimal | None, Query(ge=0)] = None,
    price_max: Annotated[Decimal | None, Query(ge=0)] = None,
    sort: Annotated[EventSortField, Query()] = EventSortField.DATE,
    order: Annotated[SortOrder, Query()] = SortOrder.ASC,
) -> EventListResponse:
    """Return the public catalogue of published, non-deleted events."""
    items, total = await service.list_events(
        db,
        page=page,
        size=size,
        search=search,
        category=category,
        tags=tag,
        date_from=date_from,
        date_to=date_to,
        price_min=price_min,
        price_max=price_max,
        sort=sort,
        order=order,
    )
    return EventListResponse(
        items=[EventRead.model_validate(event) for event in items],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/events/{event_id}",
    response_model=EventDetailRead,
    status_code=status.HTTP_200_OK,
    summary="Get a published event",
)
async def get_event(
    event_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    """Return a published, non-deleted event; otherwise 404."""
    return await service.get_event_detail(db, event_id)


# ---------------------------------------------------------------------------
# Event writes (admin / organizer)
# ---------------------------------------------------------------------------


@router.post(
    "/events",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event",
)
async def create_event(
    payload: EventCreate,
    current_user: Annotated[User, Depends(require_managed_roles)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    """Create a draft or published event owned by the authenticated organizer."""
    return await service.create_event(db, payload, organizer_id=current_user.id)


@router.patch(
    "/events/{event_id}",
    response_model=EventRead,
    status_code=status.HTTP_200_OK,
    summary="Update or transition an event",
)
async def update_event(
    payload: EventUpdate,
    current_user: Annotated[User, Depends(require_managed_roles)],
    event: Annotated[Event, Depends(get_managed_event)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    """Apply a partial update or status transition to a managed event."""
    return await service.update_event(db, event, payload, actor_id=current_user.id)


@router.delete(
    "/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Soft-delete an event",
)
async def delete_event(
    current_user: Annotated[User, Depends(require_managed_roles)],
    event: Annotated[Event, Depends(get_managed_event)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete an event and record the audit row."""
    await service.soft_delete_event(db, event, actor_id=current_user.id)


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


@router.get(
    "/categories",
    response_model=list[CategoryRead],
    status_code=status.HTTP_200_OK,
    summary="List categories",
)
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Category]:
    """Return all categories ordered by name."""
    return await service.list_categories(db)


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
)
async def create_category(
    payload: CategoryCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Category:
    """Create a category (admin only)."""
    return await service.create_category(db, payload, actor_id=current_user.id)


@router.get(
    "/tags",
    response_model=list[TagRead],
    status_code=status.HTTP_200_OK,
    summary="List tags",
)
async def list_tags(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Tag]:
    """Return all tags ordered by name."""
    return await service.list_tags(db)


@router.post(
    "/tags",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag",
)
async def create_tag(
    payload: TagCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Tag:
    """Create a tag (admin only)."""
    return await service.create_tag(db, payload, actor_id=current_user.id)
