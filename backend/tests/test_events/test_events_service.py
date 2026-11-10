import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.events import service
from app.models.category import Category
from app.models.event import Event, EventStatus
from app.models.tag import Tag
from app.models.user import User
from app.schemas.events import (
    CategoryCreate,
    EventCreate,
    EventSortField,
    EventUpdate,
    SortOrder,
)
from tests.test_events.conftest import EventFactory, unique_suffix


def _create_payload(**overrides: Any) -> EventCreate:
    suffix = unique_suffix()
    payload: dict[str, Any] = {
        "title": f"Service Event {suffix}",
        "description": "Service-level test event",
        "venue": "Service Hall",
        "starts_at": datetime.now(UTC) + timedelta(days=20),
        "price": Decimal("50.00"),
        "total_tickets": 25,
        "status": EventStatus.DRAFT,
        "tag_ids": [],
    }
    payload.update(overrides)
    return EventCreate(**payload)


@pytest.mark.asyncio
async def test_create_event_sets_tickets_available(
    db_session: AsyncSession,
    organizer_user: User,
) -> None:
    event = await service.create_event(
        db_session,
        _create_payload(total_tickets=42),
        organizer_id=organizer_user.id,
    )

    assert event.tickets_available == 42
    assert event.total_tickets == 42
    stored = await db_session.get(Event, event.id)
    assert stored is not None
    assert stored.tickets_available == 42


@pytest.mark.asyncio
async def test_create_event_rejects_missing_category_or_tags(
    db_session: AsyncSession,
    organizer_user: User,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await service.create_event(
            db_session,
            _create_payload(category_id=uuid.uuid4()),
            organizer_id=organizer_user.id,
        )
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        await service.create_event(
            db_session,
            _create_payload(tag_ids=[uuid.uuid4()]),
            organizer_id=organizer_user.id,
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_recalculates_tickets_available(
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
) -> None:
    event = await event_factory(
        organizer_user,
        total_tickets=100,
        tickets_available=90,
    )

    updated = await service.update_event(
        db_session,
        event,
        EventUpdate(total_tickets=50),
        actor_id=organizer_user.id,
    )

    # 10 tickets were sold, so 50 total leaves 40 available.
    assert updated.total_tickets == 50
    assert updated.tickets_available == 40


@pytest.mark.asyncio
async def test_update_rejects_total_tickets_below_sold(
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
) -> None:
    event = await event_factory(
        organizer_user,
        total_tickets=100,
        tickets_available=90,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_event(
            db_session,
            event,
            EventUpdate(total_tickets=5),
            actor_id=organizer_user.id,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current", "target"),
    [
        (EventStatus.DRAFT, EventStatus.PUBLISHED),
        (EventStatus.DRAFT, EventStatus.CANCELLED),
        (EventStatus.PUBLISHED, EventStatus.CANCELLED),
        (EventStatus.PUBLISHED, EventStatus.COMPLETED),
    ],
)
async def test_valid_status_transitions(
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
    current: EventStatus,
    target: EventStatus,
) -> None:
    event = await event_factory(organizer_user, status=current)
    updated = await service.update_event(
        db_session,
        event,
        EventUpdate(status=target),
        actor_id=organizer_user.id,
    )
    assert updated.status == target


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current", "target"),
    [
        (EventStatus.DRAFT, EventStatus.COMPLETED),
        (EventStatus.PUBLISHED, EventStatus.DRAFT),
        (EventStatus.CANCELLED, EventStatus.PUBLISHED),
        (EventStatus.COMPLETED, EventStatus.DRAFT),
    ],
)
async def test_invalid_status_transitions(
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
    current: EventStatus,
    target: EventStatus,
) -> None:
    event = await event_factory(organizer_user, status=current)
    with pytest.raises(HTTPException) as exc_info:
        await service.update_event(
            db_session,
            event,
            EventUpdate(status=target),
            actor_id=organizer_user.id,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", [EventStatus.CANCELLED, EventStatus.COMPLETED])
async def test_edit_on_terminal_event_is_rejected(
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
    terminal: EventStatus,
) -> None:
    event = await event_factory(organizer_user, status=terminal)
    with pytest.raises(HTTPException) as exc_info:
        await service.update_event(
            db_session,
            event,
            EventUpdate(title="Changed after terminal"),
            actor_id=organizer_user.id,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_soft_delete_hides_event_from_catalogue_and_detail(
    db_session: AsyncSession,
    organizer_user: User,
    category: Category,
    event_factory: EventFactory,
) -> None:
    event = await event_factory(organizer_user, category=category)

    await service.soft_delete_event(db_session, event, actor_id=organizer_user.id)

    items, total = await service.list_events(db_session, category=category.slug)
    assert total == 0
    assert items == []

    with pytest.raises(HTTPException) as exc_info:
        await service.get_event_detail(db_session, event.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_catalogue_filters_and_sorting(
    db_session: AsyncSession,
    organizer_user: User,
    category: Category,
    tags: list[Tag],
    event_factory: EventFactory,
) -> None:
    tag_a, tag_b = tags
    token = f"SearchToken{unique_suffix()}"
    base = datetime.now(UTC) + timedelta(days=10)
    first = await event_factory(
        organizer_user,
        category=category,
        event_tags=[tag_a],
        title=f"{token} Alpha",
        price=Decimal("10.00"),
        starts_at=base,
    )
    second = await event_factory(
        organizer_user,
        category=category,
        event_tags=[tag_b],
        title="Beta",
        price=Decimal("20.00"),
        starts_at=base + timedelta(days=5),
    )
    third = await event_factory(
        organizer_user,
        category=category,
        event_tags=[tag_a, tag_b],
        title="Gamma",
        price=Decimal("30.00"),
        starts_at=base + timedelta(days=10),
    )

    # Category filter sees every published event in this category.
    items, total = await service.list_events(db_session, category=category.slug)
    assert total == 3
    assert {event.id for event in items} == {first.id, second.id, third.id}

    # Title search.
    items, total = await service.list_events(
        db_session,
        category=category.slug,
        search=token,
    )
    assert total == 1
    assert items[0].id == first.id

    # Price range.
    items, total = await service.list_events(
        db_session,
        category=category.slug,
        price_min=Decimal("15.00"),
        price_max=Decimal("25.00"),
    )
    assert total == 1
    assert items[0].id == second.id

    # Date range.
    items, total = await service.list_events(
        db_session,
        category=category.slug,
        date_from=base + timedelta(days=4),
        date_to=base + timedelta(days=6),
    )
    assert total == 1
    assert items[0].id == second.id

    # Tag filters use OR semantics.
    _, total = await service.list_events(
        db_session,
        category=category.slug,
        tags=[tag_a.slug, tag_b.slug],
    )
    assert total == 3

    _, total = await service.list_events(
        db_session,
        category=category.slug,
        tags=[tag_b.slug],
    )
    assert total == 2

    # Sorting by price ascending and descending.
    items, _ = await service.list_events(
        db_session,
        category=category.slug,
        sort=EventSortField.PRICE,
        order=SortOrder.ASC,
    )
    assert [event.id for event in items] == [first.id, second.id, third.id]

    items, _ = await service.list_events(
        db_session,
        category=category.slug,
        sort=EventSortField.PRICE,
        order=SortOrder.DESC,
    )
    assert [event.id for event in items] == [third.id, second.id, first.id]

    # Sorting by date.
    items, _ = await service.list_events(
        db_session,
        category=category.slug,
        sort=EventSortField.DATE,
        order=SortOrder.ASC,
    )
    assert [event.id for event in items] == [first.id, second.id, third.id]


@pytest.mark.asyncio
async def test_catalogue_pagination_and_visibility(
    db_session: AsyncSession,
    organizer_user: User,
    category: Category,
    event_factory: EventFactory,
) -> None:
    published = []
    for index in range(5):
        published.append(
            await event_factory(
                organizer_user,
                category=category,
                title=f"Paged {index} {unique_suffix()}",
            )
        )
    await event_factory(
        organizer_user,
        category=category,
        status=EventStatus.DRAFT,
    )
    await event_factory(
        organizer_user,
        category=category,
        status=EventStatus.CANCELLED,
    )
    deleted = await event_factory(organizer_user, category=category)
    await service.soft_delete_event(db_session, deleted, actor_id=organizer_user.id)

    page_one, total = await service.list_events(
        db_session,
        category=category.slug,
        page=1,
        size=2,
    )
    page_two, _ = await service.list_events(
        db_session,
        category=category.slug,
        page=2,
        size=2,
    )
    page_three, _ = await service.list_events(
        db_session,
        category=category.slug,
        page=3,
        size=2,
    )
    page_four, _ = await service.list_events(
        db_session,
        category=category.slug,
        page=4,
        size=2,
    )

    assert total == 5
    assert len(page_one) == 2
    assert len(page_two) == 2
    assert len(page_three) == 1
    assert page_four == []
    assert {event.id for event in page_one + page_two + page_three} == {
        event.id for event in published
    }


@pytest.mark.asyncio
async def test_catalogue_rejects_inverted_ranges(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    with pytest.raises(HTTPException) as exc_info:
        await service.list_events(
            db_session,
            date_from=now + timedelta(days=1),
            date_to=now,
        )
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        await service.list_events(
            db_session,
            price_min=Decimal("20.00"),
            price_max=Decimal("10.00"),
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_category_slug_generation_and_duplicates(
    db_session: AsyncSession,
    admin_user: User,
) -> None:
    suffix = unique_suffix()
    created = await service.create_category(
        db_session,
        CategoryCreate(name=f"Auto Slug {suffix}"),
        actor_id=admin_user.id,
    )
    assert created.slug == f"auto-slug-{suffix}".lower()

    with pytest.raises(HTTPException) as exc_info:
        await service.create_category(
            db_session,
            CategoryCreate(name="Duplicate", slug=created.slug),
            actor_id=admin_user.id,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_generated_slug_gets_numeric_suffix(
    db_session: AsyncSession,
    admin_user: User,
) -> None:
    suffix = unique_suffix()
    name = f"Same Name {suffix}"
    first = await service.create_category(
        db_session,
        CategoryCreate(name=name),
        actor_id=admin_user.id,
    )
    second = await service.create_category(
        db_session,
        CategoryCreate(name=name),
        actor_id=admin_user.id,
    )
    assert first.slug != second.slug
    assert second.slug == f"{first.slug}-2"


@pytest.mark.asyncio
async def test_concurrent_auto_slug_creation_retries_with_suffix(
    admin_user: User,
) -> None:
    """Two concurrent creates with the same name get distinct generated slugs."""
    name = f"Concurrent Category {unique_suffix()}"
    engines = [
        create_async_engine(settings.ASYNC_DATABASE_URL, poolclass=NullPool) for _ in range(2)
    ]
    session_factories = [
        async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        for engine in engines
    ]

    async def _create(factory: async_sessionmaker) -> Category:
        async with factory() as session:
            return await service.create_category(
                session,
                CategoryCreate(name=name),
                actor_id=admin_user.id,
            )

    try:
        results = await asyncio.gather(*(_create(factory) for factory in session_factories))
    finally:
        for engine in engines:
            await engine.dispose()

    slugs = sorted(category.slug for category in results)
    expected_base = service.slugify(name)
    assert slugs == sorted([expected_base, f"{expected_base}-2"])


@pytest.mark.asyncio
async def test_auto_slug_retries_after_integrity_conflict(
    db_session: AsyncSession,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generated-slug unique conflict retries instead of returning 409."""
    suffix = unique_suffix()
    existing = await service.create_category(
        db_session,
        CategoryCreate(name=f"Existing {suffix}"),
        actor_id=admin_user.id,
    )
    existing_slug = existing.slug

    original_generator = service._generate_unique_slug
    calls = {"count": 0}

    async def _collide_once(
        db: AsyncSession,
        model: Any,
        name: str,
        *,
        max_length: int,
    ) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return existing_slug
        return await original_generator(db, model, name, max_length=max_length)

    monkeypatch.setattr(service, "_generate_unique_slug", _collide_once)

    created = await service.create_category(
        db_session,
        CategoryCreate(name=f"Retried {suffix}"),
        actor_id=admin_user.id,
    )

    assert calls["count"] >= 2
    assert created.slug != existing_slug


@pytest.mark.asyncio
async def test_list_categories_is_ordered_by_name(
    db_session: AsyncSession,
) -> None:
    categories = await service.list_categories(db_session)
    names = [category.name for category in categories]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_event_tags_are_replaced_and_cleared(
    db_session: AsyncSession,
    organizer_user: User,
    tags: list[Tag],
    event_factory: EventFactory,
) -> None:
    tag_a, tag_b = tags
    event = await event_factory(organizer_user, event_tags=[tag_a])

    updated = await service.update_event(
        db_session,
        event,
        EventUpdate(tag_ids=[tag_b.id]),
        actor_id=organizer_user.id,
    )
    assert {tag.id for tag in updated.tags} == {tag_b.id}

    updated = await service.update_event(
        db_session,
        updated,
        EventUpdate(tag_ids=[]),
        actor_id=organizer_user.id,
    )
    assert updated.tags == []


@pytest.mark.asyncio
async def test_update_ignores_omitted_fields(
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
) -> None:
    event = await event_factory(
        organizer_user,
        title="Original title",
        venue="Original venue",
        price=Decimal("12.34"),
    )
    updated = await service.update_event(
        db_session,
        event,
        EventUpdate(venue="Updated venue"),
        actor_id=organizer_user.id,
    )
    assert updated.title == "Original title"
    assert updated.venue == "Updated venue"
    assert updated.price == Decimal("12.34")


@pytest.mark.asyncio
async def test_get_event_detail_requires_published_status(
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
) -> None:
    event = await event_factory(organizer_user, status=EventStatus.DRAFT)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_event_detail(db_session, event.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_tags_is_ordered_by_name(db_session: AsyncSession) -> None:
    tags = await service.list_tags(db_session)
    names = [tag.name for tag in tags]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_soft_deleted_event_row_is_retained(
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
) -> None:
    event = await event_factory(organizer_user)
    event_id = event.id
    await service.soft_delete_event(db_session, event, actor_id=organizer_user.id)

    row = (await db_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    assert row.deleted_at is not None
