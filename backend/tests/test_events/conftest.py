import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.category import Category
from app.models.event import Event, EventStatus
from app.models.tag import Tag
from app.models.user import User, UserRole


def unique_suffix() -> str:
    """Short, collision-resistant suffix for test data."""
    return uuid.uuid4().hex[:10]


@pytest.fixture
async def category(db_session: AsyncSession) -> AsyncGenerator[Category, None]:
    """Yields a persisted category with a unique slug."""
    suffix = unique_suffix()
    category = Category(
        name=f"Category {suffix}",
        slug=f"category-{suffix}",
        description="Test category",
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    category_id = category.id
    try:
        yield category
    finally:
        await db_session.rollback()
        # The autouse taxonomy cleanup also covers rows created through the API.
        await db_session.execute(delete(Category).where(Category.id == category_id))
        await db_session.commit()


@pytest.fixture
async def tags(db_session: AsyncSession) -> AsyncGenerator[list[Tag], None]:
    """Yields two persisted tags with unique slugs."""
    suffix = unique_suffix()
    tag_rows = [
        Tag(name=f"Tag A {suffix}", slug=f"tag-a-{suffix}"),
        Tag(name=f"Tag B {suffix}", slug=f"tag-b-{suffix}"),
    ]
    db_session.add_all(tag_rows)
    await db_session.commit()
    for tag in tag_rows:
        await db_session.refresh(tag)
    tag_ids = [tag.id for tag in tag_rows]
    try:
        yield tag_rows
    finally:
        await db_session.rollback()
        await db_session.execute(delete(Tag).where(Tag.id.in_(tag_ids)))
        await db_session.commit()


@pytest.fixture
async def second_organizer(db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """Yields an organizer independent from the shared ``organizer_user`` fixture."""
    suffix = unique_suffix()
    user = User(
        email=f"second_organizer_{suffix}@example.com",
        hashed_password=hash_password("TestPassword123!"),
        full_name=f"Second Organizer {suffix}",
        role=UserRole.ORGANIZER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id
    user.headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}  # type: ignore[attr-defined]
    try:
        yield user
    finally:
        await db_session.rollback()
        await db_session.execute(delete(Event).where(Event.organizer_id == user_id))
        await db_session.execute(delete(User).where(User.id == user_id))
        await db_session.commit()


EventFactory = Callable[..., Coroutine[Any, Any, Event]]


@pytest.fixture
def event_factory(db_session: AsyncSession) -> EventFactory:
    """Returns an async factory that persists events for a given organizer."""

    async def _create(
        organizer: User,
        *,
        status: EventStatus = EventStatus.PUBLISHED,
        category: Category | None = None,
        event_tags: list[Tag] | None = None,
        title: str | None = None,
        description: str = "Test event description",
        venue: str = "Test Venue",
        starts_at: datetime | None = None,
        price: Decimal = Decimal("100.00"),
        total_tickets: int = 100,
        tickets_available: int | None = None,
    ) -> Event:
        suffix = unique_suffix()
        event = Event(
            organizer_id=organizer.id,
            category_id=category.id if category is not None else None,
            title=title or f"Test Event {suffix}",
            description=description,
            venue=venue,
            starts_at=starts_at or (datetime.now(UTC) + timedelta(days=30)),
            price=price,
            total_tickets=total_tickets,
            tickets_available=(total_tickets if tickets_available is None else tickets_available),
            status=status,
        )
        if event_tags:
            event.tags = list(event_tags)
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)
        return event

    return _create


def event_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid ``POST /events`` payload with unique defaults."""
    suffix = unique_suffix()
    payload: dict[str, Any] = {
        "title": f"Payload Event {suffix}",
        "description": "Event created from an API payload",
        "venue": "Convention Center",
        "starts_at": (datetime.now(UTC) + timedelta(days=15)).isoformat(),
        "price": "199.00",
        "total_tickets": 500,
        "status": "draft",
        "tag_ids": [],
    }
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
async def cleanup_taxonomy(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """Delete categories/tags created during the test (API or fixtures)."""
    before_categories = set((await db_session.execute(select(Category.id))).scalars().all())
    before_tags = set((await db_session.execute(select(Tag.id))).scalars().all())

    yield

    await db_session.rollback()
    after_categories = set((await db_session.execute(select(Category.id))).scalars().all())
    after_tags = set((await db_session.execute(select(Tag.id))).scalars().all())

    new_categories = after_categories - before_categories
    new_tags = after_tags - before_tags

    if new_categories:
        await db_session.execute(delete(Category).where(Category.id.in_(new_categories)))
    if new_tags:
        await db_session.execute(delete(Tag).where(Tag.id.in_(new_tags)))
    await db_session.commit()
