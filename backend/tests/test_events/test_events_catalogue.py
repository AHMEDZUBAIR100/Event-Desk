from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.category import Category
from app.models.event import EventStatus
from app.models.tag import Tag
from app.models.user import User
from tests.test_events.conftest import EventFactory, unique_suffix


async def _get_catalogue(
    client: AsyncClient,
    **params: Any,
) -> dict[str, Any]:
    response = await client.get("/api/v1/events", params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_catalogue_filters_combined(
    client: AsyncClient,
    organizer_user: User,
    category: Category,
    tags: list[Tag],
    event_factory: EventFactory,
) -> None:
    tag_a, tag_b = tags
    token = f"ComboToken{unique_suffix()}"
    base = datetime.now(UTC) + timedelta(days=30)

    match = await event_factory(
        organizer_user,
        category=category,
        event_tags=[tag_a],
        title=f"{token} Match",
        price=Decimal("75.00"),
        starts_at=base,
    )
    await event_factory(
        organizer_user,
        category=category,
        event_tags=[tag_b],
        title=f"{token} Wrong Tag",
        price=Decimal("75.00"),
        starts_at=base,
    )
    await event_factory(
        organizer_user,
        category=category,
        event_tags=[tag_a],
        title=f"{token} Wrong Price",
        price=Decimal("500.00"),
        starts_at=base,
    )
    await event_factory(
        organizer_user,
        category=category,
        event_tags=[tag_a],
        title=f"{token} Wrong Date",
        price=Decimal("75.00"),
        starts_at=base + timedelta(days=60),
    )

    body = await _get_catalogue(
        client,
        category=category.slug,
        tag=tag_a.slug,
        date_from=(base - timedelta(days=1)).isoformat(),
        date_to=(base + timedelta(days=1)).isoformat(),
        price_min="50",
        price_max="100",
        search=token,
    )

    assert body["total"] == 1
    assert body["items"][0]["id"] == str(match.id)


@pytest.mark.asyncio
async def test_catalogue_tag_filter_uses_or_semantics(
    client: AsyncClient,
    organizer_user: User,
    category: Category,
    tags: list[Tag],
    event_factory: EventFactory,
) -> None:
    tag_a, tag_b = tags
    first = await event_factory(organizer_user, category=category, event_tags=[tag_a])
    second = await event_factory(organizer_user, category=category, event_tags=[tag_b])
    third = await event_factory(organizer_user, category=category, event_tags=[tag_a, tag_b])

    body = await _get_catalogue(
        client,
        category=category.slug,
        tag=[tag_a.slug, tag_b.slug],
    )
    assert body["total"] == 3
    assert {item["id"] for item in body["items"]} == {
        str(first.id),
        str(second.id),
        str(third.id),
    }

    only_a = await _get_catalogue(client, category=category.slug, tag=tag_a.slug)
    assert only_a["total"] == 2


@pytest.mark.asyncio
async def test_catalogue_sorting(
    client: AsyncClient,
    organizer_user: User,
    category: Category,
    event_factory: EventFactory,
) -> None:
    base = datetime.now(UTC) + timedelta(days=10)
    first = await event_factory(
        organizer_user,
        category=category,
        price=Decimal("10.00"),
        starts_at=base,
    )
    second = await event_factory(
        organizer_user,
        category=category,
        price=Decimal("20.00"),
        starts_at=base + timedelta(days=1),
    )
    third = await event_factory(
        organizer_user,
        category=category,
        price=Decimal("30.00"),
        starts_at=base + timedelta(days=2),
    )

    price_asc = await _get_catalogue(client, category=category.slug, sort="price", order="asc")
    assert [item["id"] for item in price_asc["items"]] == [
        str(first.id),
        str(second.id),
        str(third.id),
    ]

    price_desc = await _get_catalogue(client, category=category.slug, sort="price", order="desc")
    assert [item["id"] for item in price_desc["items"]] == [
        str(third.id),
        str(second.id),
        str(first.id),
    ]

    date_asc = await _get_catalogue(client, category=category.slug, sort="date", order="asc")
    assert [item["id"] for item in date_asc["items"]] == [
        str(first.id),
        str(second.id),
        str(third.id),
    ]

    date_desc = await _get_catalogue(client, category=category.slug, sort="date", order="desc")
    assert [item["id"] for item in date_desc["items"]] == [
        str(third.id),
        str(second.id),
        str(first.id),
    ]


@pytest.mark.asyncio
async def test_catalogue_pagination_envelope(
    client: AsyncClient,
    organizer_user: User,
    category: Category,
    event_factory: EventFactory,
) -> None:
    created = [await event_factory(organizer_user, category=category) for _ in range(5)]

    page_one = await _get_catalogue(client, category=category.slug, page=1, size=2)
    assert page_one["page"] == 1
    assert page_one["size"] == 2
    assert page_one["total"] == 5
    assert len(page_one["items"]) == 2

    page_three = await _get_catalogue(client, category=category.slug, page=3, size=2)
    assert len(page_three["items"]) == 1

    out_of_range = await _get_catalogue(client, category=category.slug, page=4, size=2)
    assert out_of_range["total"] == 5
    assert out_of_range["items"] == []

    collected = {item["id"] for page in (page_one, page_three) for item in page["items"]}
    assert collected.issubset({str(event.id) for event in created})


@pytest.mark.asyncio
async def test_catalogue_pagination_boundaries(
    client: AsyncClient,
    category: Category,
) -> None:
    size_one = await client.get(
        "/api/v1/events",
        params={"category": category.slug, "size": 1},
    )
    assert size_one.status_code == 200

    size_hundred = await client.get(
        "/api/v1/events",
        params={"category": category.slug, "size": 100},
    )
    assert size_hundred.status_code == 200

    too_large = await client.get(
        "/api/v1/events",
        params={"category": category.slug, "size": 101},
    )
    assert too_large.status_code == 422

    zero_page = await client.get(
        "/api/v1/events",
        params={"category": category.slug, "page": 0},
    )
    assert zero_page.status_code == 422


@pytest.mark.asyncio
async def test_catalogue_invalid_ranges_return_422(
    client: AsyncClient,
) -> None:
    now = datetime.now(UTC)
    date_response = await client.get(
        "/api/v1/events",
        params={
            "date_from": (now + timedelta(days=1)).isoformat(),
            "date_to": now.isoformat(),
        },
    )
    assert date_response.status_code == 422

    price_response = await client.get(
        "/api/v1/events",
        params={"price_min": "20", "price_max": "10"},
    )
    assert price_response.status_code == 422

    invalid_sort = await client.get("/api/v1/events", params={"sort": "title"})
    assert invalid_sort.status_code == 422

    invalid_order = await client.get("/api/v1/events", params={"order": "random"})
    assert invalid_order.status_code == 422


@pytest.mark.asyncio
async def test_catalogue_unknown_slugs_return_empty_page(
    client: AsyncClient,
) -> None:
    category_body = await _get_catalogue(
        client,
        category=f"missing-{unique_suffix()}",
    )
    assert category_body["total"] == 0
    assert category_body["items"] == []

    tag_body = await _get_catalogue(client, tag=f"missing-{unique_suffix()}")
    assert tag_body["total"] == 0
    assert tag_body["items"] == []


@pytest.mark.asyncio
async def test_catalogue_hides_unpublished_and_deleted_events(
    client: AsyncClient,
    organizer_user: User,
    category: Category,
    event_factory: EventFactory,
) -> None:
    # The service-level visibility rules are also asserted in
    # test_events_service; this checks the public endpoint for a category.
    published = await event_factory(organizer_user, category=category, status=EventStatus.PUBLISHED)
    await event_factory(organizer_user, category=category, status=EventStatus.DRAFT)
    await event_factory(organizer_user, category=category, status=EventStatus.CANCELLED)
    await event_factory(organizer_user, category=category, status=EventStatus.COMPLETED)

    body = await _get_catalogue(client, category=category.slug)
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(published.id)
