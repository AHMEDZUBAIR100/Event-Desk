import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.test_events.conftest import unique_suffix


@pytest.mark.asyncio
async def test_list_categories_and_tags_are_public(
    client: AsyncClient,
    category: object,
    tags: list[object],
) -> None:
    categories_response = await client.get("/api/v1/categories")
    assert categories_response.status_code == 200
    assert isinstance(categories_response.json(), list)

    tags_response = await client.get("/api/v1/tags")
    assert tags_response.status_code == 200
    assert isinstance(tags_response.json(), list)


@pytest.mark.asyncio
async def test_admin_can_create_category_with_auto_slug(
    client: AsyncClient,
    admin_user: User,
) -> None:
    suffix = unique_suffix()
    response = await client.post(
        "/api/v1/categories",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": f"Conferences {suffix}", "description": "Conference events"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["slug"] == f"conferences-{suffix}"
    assert body["description"] == "Conference events"
    assert body["name"] == f"Conferences {suffix}"


@pytest.mark.asyncio
async def test_admin_can_create_tag_with_auto_slug(
    client: AsyncClient,
    admin_user: User,
) -> None:
    suffix = unique_suffix()
    response = await client.post(
        "/api/v1/tags",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": f"Python {suffix}"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["slug"] == f"python-{suffix}"
    assert body["name"] == f"Python {suffix}"


@pytest.mark.asyncio
async def test_explicit_slug_is_used(
    client: AsyncClient,
    admin_user: User,
) -> None:
    suffix = unique_suffix()
    response = await client.post(
        "/api/v1/categories",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": "Explicit", "slug": f"explicit-{suffix}"},
    )
    assert response.status_code == 201
    assert response.json()["slug"] == f"explicit-{suffix}"


@pytest.mark.asyncio
async def test_duplicate_slug_returns_409(
    client: AsyncClient,
    admin_user: User,
) -> None:
    category_response = await client.post(
        "/api/v1/categories",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": f"First {unique_suffix()}"},
    )
    assert category_response.status_code == 201
    slug = category_response.json()["slug"]

    duplicate_category = await client.post(
        "/api/v1/categories",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": "Second", "slug": slug},
    )
    assert duplicate_category.status_code == 409

    tag_response = await client.post(
        "/api/v1/tags",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": f"First Tag {unique_suffix()}"},
    )
    assert tag_response.status_code == 201
    tag_slug = tag_response.json()["slug"]

    duplicate_tag = await client.post(
        "/api/v1/tags",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": "Second Tag", "slug": tag_slug},
    )
    assert duplicate_tag.status_code == 409


@pytest.mark.asyncio
async def test_taxonomy_create_rbac(
    client: AsyncClient,
    organizer_user: User,
    attendee_user: User,
) -> None:
    payload = {"name": f"RBAC {unique_suffix()}"}

    for user in (organizer_user, attendee_user):
        response = await client.post(
            "/api/v1/categories",
            headers=user.headers,  # type: ignore[attr-defined]
            json=payload,
        )
        assert response.status_code == 403

        tag_response = await client.post(
            "/api/v1/tags",
            headers=user.headers,  # type: ignore[attr-defined]
            json=payload,
        )
        assert tag_response.status_code == 403

    assert (await client.post("/api/v1/categories", json=payload)).status_code == 401
    assert (await client.post("/api/v1/tags", json=payload)).status_code == 401


@pytest.mark.asyncio
async def test_taxonomy_validation_errors(
    client: AsyncClient,
    admin_user: User,
) -> None:
    empty_name = await client.post(
        "/api/v1/categories",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": ""},
    )
    assert empty_name.status_code == 422

    long_name = await client.post(
        "/api/v1/tags",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": "x" * 51},
    )
    assert long_name.status_code == 422

    long_category_name = await client.post(
        "/api/v1/categories",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"name": "x" * 101},
    )
    assert long_category_name.status_code == 422
