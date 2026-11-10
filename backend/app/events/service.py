import re
import unicodedata
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditLog
from app.models.category import Category
from app.models.event import Event, EventStatus
from app.models.tag import Tag
from app.schemas.events import (
    CategoryCreate,
    EventCreate,
    EventSortField,
    EventUpdate,
    SortOrder,
    TagCreate,
)

#: Relations that every event response needs. ``selectinload`` is used instead
#: of ``joinedload`` so row-locking queries never lock foreign-table rows.
_EVENT_LOAD_OPTIONS = (
    selectinload(Event.category),
    selectinload(Event.tags),
    selectinload(Event.organizer),
)

#: Explicit status machine (D2). Cancelled and completed are terminal.
_ALLOWED_TRANSITIONS: dict[EventStatus, set[EventStatus]] = {
    EventStatus.DRAFT: {EventStatus.PUBLISHED, EventStatus.CANCELLED},
    EventStatus.PUBLISHED: {EventStatus.CANCELLED, EventStatus.COMPLETED},
    EventStatus.CANCELLED: set(),
    EventStatus.COMPLETED: set(),
}

_EDITABLE_STATUSES = (EventStatus.DRAFT, EventStatus.PUBLISHED)

#: Max retries when a concurrently created row wins the generated-slug race.
_MAX_SLUG_ATTEMPTS = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_utc(value: datetime) -> datetime:
    """Return a timezone-aware datetime, assuming UTC for naive inputs."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so users cannot inject pattern characters."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def slugify(value: str) -> str:
    """Generate a URL-safe slug using only the standard library."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "item"


def _audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Stage an audit row in the caller's current transaction."""
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata or {},
        )
    )


async def _load_event_with_relations(
    db: AsyncSession,
    event_id: uuid.UUID,
    *,
    populate_existing: bool = False,
) -> Event:
    """Reload an event with category, tags, and organizer eagerly loaded."""
    stmt: Select[tuple[Event]] = (
        select(Event).where(Event.id == event_id).options(*_EVENT_LOAD_OPTIONS)
    )
    if populate_existing:
        stmt = stmt.execution_options(populate_existing=True)
    event = (await db.execute(stmt)).scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' was not found.",
        )
    return event


async def _get_category_or_422(
    db: AsyncSession,
    category_id: uuid.UUID | None,
) -> Category | None:
    if category_id is None:
        return None
    category = await db.get(Category, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Category with id '{category_id}' does not exist.",
        )
    return category


async def _get_tags_or_422(
    db: AsyncSession,
    tag_ids: list[uuid.UUID],
) -> list[Tag]:
    if not tag_ids:
        return []
    unique_ids = list(dict.fromkeys(tag_ids))
    tags = list(
        (await db.execute(select(Tag).where(Tag.id.in_(unique_ids)).order_by(Tag.name)))
        .scalars()
        .all()
    )
    found_ids = {tag.id for tag in tags}
    missing = [str(tag_id) for tag_id in unique_ids if tag_id not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Tag(s) not found: {', '.join(missing)}.",
        )
    return tags


def _validate_transition(current: EventStatus, target: EventStatus) -> None:
    """Validate a status transition; same-status PATCH is an idempotent no-op."""
    if target == current:
        return
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid status transition '{current.value}' -> '{target.value}'. "
                f"Allowed from '{current.value}': "
                f"{sorted(item.value for item in _ALLOWED_TRANSITIONS[current]) or 'none'}."
            ),
        )


async def _generate_unique_slug(
    db: AsyncSession,
    model: type[Category] | type[Tag],
    name: str,
    *,
    max_length: int,
) -> str:
    """Build a slug from ``name`` and add a numeric suffix until it is unique."""
    base = slugify(name)[:max_length]
    candidate = base
    counter = 2
    while await db.scalar(select(model.id).where(model.slug == candidate)):
        suffix = f"-{counter}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
        counter += 1
    return candidate


async def _ensure_slug_available(
    db: AsyncSession,
    model: type[Category] | type[Tag],
    slug: str,
) -> None:
    exists = await db.scalar(select(model.id).where(model.slug == slug))
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug '{slug}' is already in use.",
        )


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


async def list_events(
    db: AsyncSession,
    *,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    sort: EventSortField = EventSortField.DATE,
    order: SortOrder = SortOrder.ASC,
) -> tuple[list[Event], int]:
    """Return published, non-deleted events matching the catalogue filters."""
    if date_from is not None and date_to is not None:
        date_from = _ensure_utc(date_from)
        date_to = _ensure_utc(date_to)
        if date_from > date_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="'date_from' must be earlier than or equal to 'date_to'.",
            )
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'price_min' must be lower than or equal to 'price_max'.",
        )

    conditions: list[Any] = [
        Event.status == EventStatus.PUBLISHED,
        Event.deleted_at.is_(None),
    ]

    if search:
        conditions.append(Event.title.ilike(f"%{_escape_like(search)}%", escape="\\"))
    if category:
        conditions.append(Event.category.has(Category.slug == category))
    if tags:
        cleaned_tags = [tag for tag in tags if tag]
        if cleaned_tags:
            # Repeatable ``tag`` parameters use OR semantics.
            conditions.append(Event.tags.any(Tag.slug.in_(cleaned_tags)))
    if date_from is not None:
        conditions.append(Event.starts_at >= _ensure_utc(date_from))
    if date_to is not None:
        conditions.append(Event.starts_at <= _ensure_utc(date_to))
    if price_min is not None:
        conditions.append(Event.price >= price_min)
    if price_max is not None:
        conditions.append(Event.price <= price_max)

    total = int(
        (await db.execute(select(func.count()).select_from(Event).where(*conditions))).scalar_one()
    )

    sort_column = Event.starts_at if sort == EventSortField.DATE else Event.price
    ordering = sort_column.desc() if order == SortOrder.DESC else sort_column.asc()

    items_stmt = (
        select(Event)
        .where(*conditions)
        .options(*_EVENT_LOAD_OPTIONS)
        .order_by(ordering, Event.id.asc())
        .limit(size)
        .offset((page - 1) * size)
    )
    items = list((await db.execute(items_stmt)).scalars().all())
    return items, total


async def get_event_detail(db: AsyncSession, event_id: uuid.UUID) -> Event:
    """Return a published, non-deleted event or raise 404."""
    stmt = (
        select(Event)
        .where(
            Event.id == event_id,
            Event.status == EventStatus.PUBLISHED,
            Event.deleted_at.is_(None),
        )
        .options(*_EVENT_LOAD_OPTIONS)
    )
    event = (await db.execute(stmt)).scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' was not found.",
        )
    return event


async def get_event_with_lock(db: AsyncSession, event_id: uuid.UUID) -> Event:
    """Load a non-deleted event with ``SELECT ... FOR UPDATE`` or raise 404."""
    stmt = (
        select(Event)
        .where(Event.id == event_id, Event.deleted_at.is_(None))
        .options(*_EVENT_LOAD_OPTIONS)
        .with_for_update()
    )
    event = (await db.execute(stmt)).scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' was not found.",
        )
    return event


# ---------------------------------------------------------------------------
# Event writes
# ---------------------------------------------------------------------------


async def create_event(
    db: AsyncSession,
    payload: EventCreate,
    organizer_id: uuid.UUID,
) -> Event:
    """Create an event, setting ``tickets_available`` to ``total_tickets``."""
    category = await _get_category_or_422(db, payload.category_id)
    tags = await _get_tags_or_422(db, payload.tag_ids)

    event = Event(
        organizer_id=organizer_id,
        title=payload.title,
        description=payload.description,
        venue=payload.venue,
        starts_at=_ensure_utc(payload.starts_at),
        price=payload.price,
        total_tickets=payload.total_tickets,
        tickets_available=payload.total_tickets,
        status=payload.status,
    )
    event.category = category
    event.tags = tags
    db.add(event)
    await db.flush()

    _audit(
        db,
        action="EVENT_CREATE",
        entity_type="Event",
        entity_id=event.id,
        actor_id=organizer_id,
        metadata={"title": event.title, "status": event.status.value},
    )

    await db.commit()
    return await _load_event_with_relations(db, event.id, populate_existing=True)


async def update_event(
    db: AsyncSession,
    event: Event,
    payload: EventUpdate,
    actor_id: uuid.UUID,
) -> Event:
    """Apply a partial update, enforcing edit and status-transition rules."""
    changed_fields = payload.model_fields_set
    if not changed_fields:
        return event

    # PATCHing only the current status is an idempotent no-op, even for
    # terminal events: no timestamp change, no audit row, no commit.
    if changed_fields == {"status"} and payload.status == event.status:
        return event

    if event.status not in _EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Events in status '{event.status.value}' cannot be edited.",
        )

    old_status = event.status
    target_status = payload.status if "status" in changed_fields else None
    if target_status is not None:
        _validate_transition(old_status, target_status)

    new_total = payload.total_tickets if "total_tickets" in changed_fields else None
    new_tickets_available: int | None = None
    if new_total is not None:
        sold = event.total_tickets - event.tickets_available
        if new_total < sold:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"'total_tickets' ({new_total}) cannot be lower than the "
                    f"{sold} ticket(s) already sold."
                ),
            )
        new_tickets_available = new_total - sold

    # Replacing a relationship collection requires it to be loaded first;
    # async sessions cannot lazy-load during attribute assignment.
    if "tag_ids" in changed_fields:
        await db.refresh(event, attribute_names=["tags"])

    category = (
        await _get_category_or_422(db, payload.category_id)
        if "category_id" in changed_fields
        else None
    )
    tags = (
        await _get_tags_or_422(db, payload.tag_ids or []) if "tag_ids" in changed_fields else None
    )

    scalar_fields = (
        "title",
        "description",
        "venue",
        "starts_at",
        "price",
        "total_tickets",
        "status",
    )
    for field_name in scalar_fields:
        if field_name not in changed_fields:
            continue
        value = getattr(payload, field_name)
        if field_name == "starts_at":
            value = _ensure_utc(value)
        setattr(event, field_name, value)

    if new_tickets_available is not None:
        event.tickets_available = new_tickets_available

    if "category_id" in changed_fields:
        event.category = category
    if "tag_ids" in changed_fields:
        event.tags = tags or []

    event.updated_at = datetime.now(UTC)

    audit_metadata: dict[str, Any] = {"changed_fields": sorted(changed_fields)}
    if target_status is not None and target_status != old_status:
        audit_metadata["old_status"] = old_status.value
        audit_metadata["new_status"] = target_status.value
    action = (
        "EVENT_CANCEL"
        if target_status == EventStatus.CANCELLED and old_status != EventStatus.CANCELLED
        else "EVENT_UPDATE"
    )
    _audit(
        db,
        action=action,
        entity_type="Event",
        entity_id=event.id,
        actor_id=actor_id,
        metadata=audit_metadata,
    )

    await db.commit()
    return await _load_event_with_relations(db, event.id, populate_existing=True)


async def soft_delete_event(db: AsyncSession, event: Event, actor_id: uuid.UUID) -> None:
    """Soft-delete an event and record the audit row atomically."""
    event.deleted_at = datetime.now(UTC)
    event.updated_at = datetime.now(UTC)

    _audit(
        db,
        action="EVENT_DELETE",
        entity_type="Event",
        entity_id=event.id,
        actor_id=actor_id,
        metadata={"title": event.title, "status": event.status.value},
    )

    await db.commit()


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


async def list_categories(db: AsyncSession) -> list[Category]:
    """Return all categories ordered by name."""
    stmt = select(Category).order_by(Category.name.asc(), Category.id.asc())
    return list((await db.execute(stmt)).scalars().all())


async def _create_category_with_generated_slug(
    db: AsyncSession,
    payload: CategoryCreate,
) -> Category:
    """Insert a category, retrying with the next suffix when a slug race is lost."""
    for _ in range(_MAX_SLUG_ATTEMPTS):
        slug = await _generate_unique_slug(db, Category, payload.name, max_length=120)
        category = Category(
            name=payload.name,
            slug=slug,
            description=payload.description,
        )
        db.add(category)
        try:
            await db.flush()
            return category
        except IntegrityError:
            # Another transaction committed the same generated slug first.
            # Roll back and recompute the next available suffix.
            await db.rollback()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Could not allocate a unique category slug; please retry.",
    )


async def create_category(
    db: AsyncSession,
    payload: CategoryCreate,
    actor_id: uuid.UUID,
) -> Category:
    """Create a category with an optional explicit or auto-generated slug."""
    if payload.slug is not None:
        # An explicitly supplied slug is never rewritten; duplicates are 409.
        await _ensure_slug_available(db, Category, payload.slug)
        category = Category(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
        db.add(category)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{payload.slug}' is already in use.",
            ) from exc
    else:
        category = await _create_category_with_generated_slug(db, payload)

    _audit(
        db,
        action="CATEGORY_CREATE",
        entity_type="Category",
        entity_id=category.id,
        actor_id=actor_id,
        metadata={"name": category.name, "slug": category.slug},
    )

    await db.commit()
    await db.refresh(category)
    return category


async def list_tags(db: AsyncSession) -> list[Tag]:
    """Return all tags ordered by name."""
    stmt = select(Tag).order_by(Tag.name.asc(), Tag.id.asc())
    return list((await db.execute(stmt)).scalars().all())


async def _create_tag_with_generated_slug(
    db: AsyncSession,
    payload: TagCreate,
) -> Tag:
    """Insert a tag, retrying with the next suffix when a slug race is lost."""
    for _ in range(_MAX_SLUG_ATTEMPTS):
        slug = await _generate_unique_slug(db, Tag, payload.name, max_length=60)
        tag = Tag(name=payload.name, slug=slug)
        db.add(tag)
        try:
            await db.flush()
            return tag
        except IntegrityError:
            # Another transaction committed the same generated slug first.
            await db.rollback()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Could not allocate a unique tag slug; please retry.",
    )


async def create_tag(
    db: AsyncSession,
    payload: TagCreate,
    actor_id: uuid.UUID,
) -> Tag:
    """Create a tag with an optional explicit or auto-generated slug."""
    if payload.slug is not None:
        # An explicitly supplied slug is never rewritten; duplicates are 409.
        await _ensure_slug_available(db, Tag, payload.slug)
        tag = Tag(name=payload.name, slug=payload.slug)
        db.add(tag)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{payload.slug}' is already in use.",
            ) from exc
    else:
        tag = await _create_tag_with_generated_slug(db, payload)

    _audit(
        db,
        action="TAG_CREATE",
        entity_type="Tag",
        entity_id=tag.id,
        actor_id=actor_id,
        metadata={"name": tag.name, "slug": tag.slug},
    )

    await db.commit()
    await db.refresh(tag)
    return tag
