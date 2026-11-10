import uuid
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.category import Category
from app.models.event import Event, EventStatus
from app.models.tag import Tag
from app.models.user import User
from tests.test_events.conftest import EventFactory, event_payload


async def _create_event(
    client: AsyncClient,
    user: User,
    **overrides: Any,
) -> dict[str, Any]:
    payload = event_payload(**overrides)
    response = await client.post(
        "/api/v1/events",
        headers=user.headers,  # type: ignore[attr-defined]
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _audit_actions(
    db_session: AsyncSession,
    event_id: uuid.UUID,
) -> list[str]:
    rows = (
        (
            await db_session.execute(
                select(AuditLog)
                .where(
                    AuditLog.entity_type == "Event",
                    AuditLog.entity_id == event_id,
                )
                .order_by(AuditLog.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [row.action for row in rows]


@pytest.mark.asyncio
async def test_create_event_rbac_matrix(
    client: AsyncClient,
    admin_user: User,
    organizer_user: User,
    attendee_user: User,
) -> None:
    admin_event = await _create_event(client, admin_user)
    organizer_event = await _create_event(client, organizer_user)

    assert admin_event["organizer"]["id"] == str(admin_user.id)
    assert organizer_event["organizer"]["id"] == str(organizer_user.id)

    attendee_response = await client.post(
        "/api/v1/events",
        headers=attendee_user.headers,  # type: ignore[attr-defined]
        json=event_payload(),
    )
    assert attendee_response.status_code == 403

    anonymous_response = await client.post("/api/v1/events", json=event_payload())
    assert anonymous_response.status_code == 401


@pytest.mark.asyncio
async def test_create_event_sets_tickets_available_and_relations(
    client: AsyncClient,
    organizer_user: User,
    category: Category,
    tags: list[Tag],
) -> None:
    data = await _create_event(
        client,
        organizer_user,
        status="published",
        category_id=str(category.id),
        tag_ids=[str(tag.id) for tag in tags],
        total_tickets=500,
        price="199.00",
    )

    assert data["tickets_available"] == 500
    assert data["total_tickets"] == 500
    assert data["status"] == "published"
    assert data["price"] == "199.00"
    assert data["category"]["id"] == str(category.id)
    assert {tag["id"] for tag in data["tags"]} == {str(tag.id) for tag in tags}
    assert "deleted_at" not in data


@pytest.mark.asyncio
async def test_idor_organizer_cannot_modify_another_organizers_event(
    client: AsyncClient,
    organizer_user: User,
    second_organizer: User,
) -> None:
    event = await _create_event(client, organizer_user, status="published")

    patch_response = await client.patch(
        f"/api/v1/events/{event['id']}",
        headers=second_organizer.headers,  # type: ignore[attr-defined]
        json={"title": "Hijacked"},
    )
    assert patch_response.status_code == 403

    delete_response = await client.delete(
        f"/api/v1/events/{event['id']}",
        headers=second_organizer.headers,  # type: ignore[attr-defined]
    )
    assert delete_response.status_code == 403


@pytest.mark.asyncio
async def test_patch_rbac_matrix(
    client: AsyncClient,
    admin_user: User,
    organizer_user: User,
    attendee_user: User,
    event_factory: EventFactory,
) -> None:
    organizer_event = await event_factory(organizer_user, status=EventStatus.PUBLISHED)
    admin_event = await event_factory(admin_user, status=EventStatus.PUBLISHED)

    admin_response = await client.patch(
        f"/api/v1/events/{organizer_event.id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"title": "Admin edited"},
    )
    assert admin_response.status_code == 200

    owner_response = await client.patch(
        f"/api/v1/events/{admin_event.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"title": "Organizer edited own event"},
    )
    assert owner_response.status_code == 403

    admin_owner_response = await client.patch(
        f"/api/v1/events/{admin_event.id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
        json={"title": "Owner edited"},
    )
    assert admin_owner_response.status_code == 200

    attendee_response = await client.patch(
        f"/api/v1/events/{organizer_event.id}",
        headers=attendee_user.headers,  # type: ignore[attr-defined]
        json={"title": "Attendee edited"},
    )
    assert attendee_response.status_code == 403

    anonymous_response = await client.patch(
        f"/api/v1/events/{organizer_event.id}",
        json={"title": "Anonymous edited"},
    )
    assert anonymous_response.status_code == 401


@pytest.mark.asyncio
async def test_patch_status_transitions_through_api(
    client: AsyncClient,
    organizer_user: User,
    event_factory: EventFactory,
) -> None:
    draft = await event_factory(organizer_user, status=EventStatus.DRAFT)
    published = await event_factory(organizer_user, status=EventStatus.PUBLISHED)

    draft_response = await client.patch(
        f"/api/v1/events/{draft.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"status": "published"},
    )
    assert draft_response.status_code == 200
    assert draft_response.json()["status"] == "published"

    cancel_response = await client.patch(
        f"/api/v1/events/{published.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"status": "cancelled"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    invalid_response = await client.patch(
        f"/api/v1/events/{published.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"status": "published"},
    )
    assert invalid_response.status_code == 409

    draft_to_completed = await event_factory(organizer_user, status=EventStatus.DRAFT)
    invalid_transition = await client.patch(
        f"/api/v1/events/{draft_to_completed.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"status": "completed"},
    )
    assert invalid_transition.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        EventStatus.DRAFT,
        EventStatus.PUBLISHED,
        EventStatus.CANCELLED,
        EventStatus.COMPLETED,
    ],
)
async def test_patch_current_status_is_noop(
    client: AsyncClient,
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
    status: EventStatus,
) -> None:
    event = await event_factory(organizer_user, status=status)
    original_updated_at = event.updated_at
    audit_before = await _audit_actions(db_session, event.id)

    response = await client.patch(
        f"/api/v1/events/{event.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"status": status.value},
    )

    assert response.status_code == 200
    assert response.json()["status"] == status.value

    stored_updated_at = (
        await db_session.execute(select(Event.updated_at).where(Event.id == event.id))
    ).scalar_one()
    assert stored_updated_at == original_updated_at

    audit_after = await _audit_actions(db_session, event.id)
    assert audit_after == audit_before


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [EventStatus.CANCELLED, EventStatus.COMPLETED])
async def test_field_edit_on_terminal_event_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
    status: EventStatus,
) -> None:
    event = await event_factory(organizer_user, status=status)
    audit_before = await _audit_actions(db_session, event.id)

    response = await client.patch(
        f"/api/v1/events/{event.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"title": "Edit after terminal"},
    )

    assert response.status_code == 409
    assert await _audit_actions(db_session, event.id) == audit_before


@pytest.mark.asyncio
async def test_delete_rbac_matrix(
    client: AsyncClient,
    admin_user: User,
    organizer_user: User,
    attendee_user: User,
    event_factory: EventFactory,
) -> None:
    organizer_event = await event_factory(organizer_user)
    admin_event = await event_factory(admin_user)

    attendee_response = await client.delete(
        f"/api/v1/events/{organizer_event.id}",
        headers=attendee_user.headers,  # type: ignore[attr-defined]
    )
    assert attendee_response.status_code == 403

    anonymous_response = await client.delete(f"/api/v1/events/{organizer_event.id}")
    assert anonymous_response.status_code == 401

    owner_response = await client.delete(
        f"/api/v1/events/{organizer_event.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
    )
    assert owner_response.status_code == 204

    admin_response = await client.delete(
        f"/api/v1/events/{admin_event.id}",
        headers=admin_user.headers,  # type: ignore[attr-defined]
    )
    assert admin_response.status_code == 204


@pytest.mark.asyncio
async def test_delete_soft_deletes_and_hides_event(
    client: AsyncClient,
    db_session: AsyncSession,
    organizer_user: User,
    category: Category,
    event_factory: EventFactory,
) -> None:
    event = await event_factory(organizer_user, category=category)
    event_id = event.id

    response = await client.delete(
        f"/api/v1/events/{event_id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
    )
    assert response.status_code == 204

    detail = await client.get(f"/api/v1/events/{event_id}")
    assert detail.status_code == 404

    catalogue = await client.get(f"/api/v1/events?category={category.slug}")
    assert catalogue.status_code == 200
    assert catalogue.json()["total"] == 0

    row = (await db_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    assert row.deleted_at is not None

    second_delete = await client.delete(
        f"/api/v1/events/{event_id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
    )
    assert second_delete.status_code == 404


@pytest.mark.asyncio
async def test_audit_rows_for_event_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
    organizer_user: User,
    event_factory: EventFactory,
) -> None:
    event = await event_factory(organizer_user, status=EventStatus.DRAFT)

    update_response = await client.patch(
        f"/api/v1/events/{event.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"title": "Audited update"},
    )
    assert update_response.status_code == 200

    cancel_response = await client.patch(
        f"/api/v1/events/{event.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"status": "cancelled"},
    )
    assert cancel_response.status_code == 200

    delete_response = await client.delete(
        f"/api/v1/events/{event.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
    )
    assert delete_response.status_code == 204

    actions = await _audit_actions(db_session, event.id)
    assert sorted(actions) == sorted(["EVENT_UPDATE", "EVENT_CANCEL", "EVENT_DELETE"])

    audit_rows = (
        (await db_session.execute(select(AuditLog).where(AuditLog.entity_id == event.id)))
        .scalars()
        .all()
    )
    assert all(row.actor_id == organizer_user.id for row in audit_rows)
    assert any(
        row.metadata_json.get("old_status") == "draft"
        and row.metadata_json.get("new_status") == "cancelled"
        for row in audit_rows
    )


@pytest.mark.asyncio
async def test_create_audit_row(
    client: AsyncClient,
    db_session: AsyncSession,
    organizer_user: User,
) -> None:
    data = await _create_event(client, organizer_user)
    actions = await _audit_actions(db_session, uuid.UUID(data["id"]))
    assert actions == ["EVENT_CREATE"]


@pytest.mark.asyncio
async def test_validation_errors(
    client: AsyncClient,
    organizer_user: User,
    category: Category,
) -> None:
    headers = organizer_user.headers  # type: ignore[attr-defined]

    negative_price = await client.post(
        "/api/v1/events",
        headers=headers,
        json=event_payload(price="-1.00"),
    )
    assert negative_price.status_code == 422

    negative_tickets = await client.post(
        "/api/v1/events",
        headers=headers,
        json=event_payload(total_tickets=-1),
    )
    assert negative_tickets.status_code == 422

    empty_title = await client.post(
        "/api/v1/events",
        headers=headers,
        json=event_payload(title=""),
    )
    assert empty_title.status_code == 422

    malformed_uuid = await client.post(
        "/api/v1/events",
        headers=headers,
        json=event_payload(category_id="not-a-uuid"),
    )
    assert malformed_uuid.status_code == 422

    missing_category = await client.post(
        "/api/v1/events",
        headers=headers,
        json=event_payload(category_id=str(uuid.uuid4())),
    )
    assert missing_category.status_code == 422

    missing_tag = await client.post(
        "/api/v1/events",
        headers=headers,
        json=event_payload(tag_ids=[str(uuid.uuid4())]),
    )
    assert missing_tag.status_code == 422

    invalid_creation_status = await client.post(
        "/api/v1/events",
        headers=headers,
        json=event_payload(status="completed"),
    )
    assert invalid_creation_status.status_code == 422


@pytest.mark.asyncio
async def test_patch_null_semantics(
    client: AsyncClient,
    organizer_user: User,
    category: Category,
    tags: list[Tag],
    event_factory: EventFactory,
) -> None:
    event = await event_factory(
        organizer_user,
        category=category,
        event_tags=tags,
        status=EventStatus.PUBLISHED,
    )
    headers = organizer_user.headers  # type: ignore[attr-defined]

    # Omitted fields remain unchanged.
    response = await client.patch(
        f"/api/v1/events/{event.id}",
        headers=headers,
        json={"venue": "New venue"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == event.title
    assert body["venue"] == "New venue"
    assert body["price"] == f"{Decimal(event.price):.2f}"

    # Explicit null clears the category.
    clear_category = await client.patch(
        f"/api/v1/events/{event.id}",
        headers=headers,
        json={"category_id": None},
    )
    assert clear_category.status_code == 200
    assert clear_category.json()["category"] is None

    # tag_ids: [] clears all tags.
    clear_tags = await client.patch(
        f"/api/v1/events/{event.id}",
        headers=headers,
        json={"tag_ids": []},
    )
    assert clear_tags.status_code == 200
    assert clear_tags.json()["tags"] == []

    for field in (
        "title",
        "description",
        "venue",
        "starts_at",
        "price",
        "total_tickets",
        "status",
        "tag_ids",
    ):
        invalid_null = await client.patch(
            f"/api/v1/events/{event.id}",
            headers=headers,
            json={field: None},
        )
        assert invalid_null.status_code == 422, field


@pytest.mark.asyncio
async def test_public_visibility_rules(
    client: AsyncClient,
    organizer_user: User,
    category: Category,
    event_factory: EventFactory,
) -> None:
    draft = await event_factory(organizer_user, category=category, status=EventStatus.DRAFT)
    cancelled = await event_factory(organizer_user, category=category, status=EventStatus.CANCELLED)
    completed = await event_factory(organizer_user, category=category, status=EventStatus.COMPLETED)
    published = await event_factory(organizer_user, category=category, status=EventStatus.PUBLISHED)

    for hidden in (draft, cancelled, completed):
        response = await client.get(f"/api/v1/events/{hidden.id}")
        assert response.status_code == 404

    visible = await client.get(f"/api/v1/events/{published.id}")
    assert visible.status_code == 200
    assert visible.json()["id"] == str(published.id)

    catalogue = await client.get(f"/api/v1/events?category={category.slug}")
    assert catalogue.status_code == 200
    assert catalogue.json()["total"] == 1
    assert catalogue.json()["items"][0]["id"] == str(published.id)


@pytest.mark.asyncio
async def test_get_event_malformed_uuid(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_missing_event_returns_404(
    client: AsyncClient,
    organizer_user: User,
) -> None:
    response = await client.patch(
        f"/api/v1/events/{uuid.uuid4()}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"title": "Ghost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_total_tickets_below_sold_through_api(
    client: AsyncClient,
    organizer_user: User,
    event_factory: EventFactory,
) -> None:
    event = await event_factory(
        organizer_user,
        status=EventStatus.PUBLISHED,
        total_tickets=100,
        tickets_available=90,
    )
    response = await client.patch(
        f"/api/v1/events/{event.id}",
        headers=organizer_user.headers,  # type: ignore[attr-defined]
        json={"total_tickets": 5},
    )
    assert response.status_code == 409
