# Implementation Proposal: Day 2 – Events API (CRUD, Catalogue, Categories & Tags)

**Status**: `IMPLEMENTED` (Day 2 backend, 2026-11-10)
**Scope**: `app/events` – event create/edit/cancel/soft-delete, status transitions, categories & tags, public catalogue with filters/sorting/pagination, tests.
**Prerequisite**: Day 1 auth & users work is implemented and green (`pytest -q` passing, Ruff clean, `alembic check` clean). The initial Alembic migration already creates `categories`, `tags`, `event_tags`, and `events`; no schema changes are required for this plan.

---

## 1. Overview & Objectives

Implement the events domain defined in `docs/API_CONTRACT.md` §3 and `docs/ERD.md`:

1. **Event management**: create (admin/organizer), edit, cancel, and soft-delete (admin any event, organizer own events only).
2. **Categories & tags**: public reads, admin-only creation, event assignment, and catalogue filtering.
3. **Status machine**: `draft`, `published`, `cancelled`, `completed` with explicit, validated transitions.
4. **Public catalogue** (`GET /events`): published, non-deleted events only, with pagination, filters (category, tag, date range, price range, title search), and sorting (date, price).
5. **Event detail** (`GET /events/{id}`): published event with category, tags, organizer summary, and live `tickets_available`.
6. **Invariant**: creating an event sets `tickets_available = total_tickets`.
7. **Soft delete**: `deleted_at` is set on delete; all default queries exclude soft-deleted rows.
8. **Audit trail**: create/update/cancel/soft-delete insert `audit_logs` rows.
9. **Tests**: service-level and endpoint-level coverage for RBAC, IDOR, transitions, filters, sorting, pagination, and soft delete.

Out of scope for this iteration: cancel notifications / Celery / WebSocket fan-out (Day 4), booking integration (Day 3), reviews summary in the detail response (Day 4), category/tag update & delete, an admin event-management listing, and the frontend.

---

## 2. Decisions Adopted by This Plan

The Day 2 prompt leaves several API details open. The following decisions are fixed for this implementation and must be reflected consistently in the API contract and tests.

| # | Decision | Default adopted |
| :--- | :--- | :--- |
| D1 | Cancel mechanism | `PATCH /events/{id}` with `{"status": "cancelled"}`. No separate `/cancel` endpoint; one write path for edits and transitions. Day 4 hooks notifications to the service-level transition. |
| D2 | Status transitions | `draft → {published, cancelled}`; `published → {cancelled, completed}`; `cancelled` and `completed` are terminal. Create allows `draft` (default) or `published`. Invalid transition → `409`. |
| D3 | Edit restrictions | Field edits are allowed only while the event is `draft` or `published`; editing a `cancelled`/`completed` event → `409`. |
| D4 | `total_tickets` updates | `sold = old_total_tickets - old_tickets_available`; reject updates where `new_total_tickets < sold` (`409`); otherwise set `tickets_available = new_total_tickets - sold`. With no bookings yet this reduces to `tickets_available = total_tickets`, and it stays correct after Day 3. |
| D5 | Taxonomy endpoints | `GET /categories` and `GET /tags` are public; `POST /categories` and `POST /tags` are admin-only. Events reference `category_id` (UUID) and `tag_ids` (list of UUIDs). Slugs are unique and auto-generated from the name when omitted. No update/delete in this iteration. |
| D6 | Catalogue filters | `category` = category slug; `tag` = tag slug (repeatable, OR semantics); `date_from` / `date_to` = ISO 8601 applied to `starts_at`; `price_min` / `price_max` = decimal; `search` = case-insensitive title match. The old `status` filter is removed because the public list is always `published`. |
| D7 | Pagination | `page` (≥ 1, default 1) and `size` (1–100, default 20). Response envelope: `{items, total, page, size}`. |
| D8 | Sorting | `sort=date|price` (default `date`) and `order=asc|desc` (default `asc`). Tie-break by `id` for deterministic pages. |
| D9 | Public detail visibility | `GET /events/{id}` returns only published, non-deleted events; draft/cancelled/completed and soft-deleted events return `404`. |
| D10 | Serialization | `price` is a `Decimal` and serializes as a JSON string (`"199.00"`) under Pydantic v2. `EventRead` nests `category`, `tags`, and `organizer` summary; it never exposes `deleted_at`. |
| D11 | Audit timing | Insert each audit row in the same database transaction as its event or taxonomy change. Commit the domain change and audit row atomically. External side effects, when introduced in a later task, run only after commit per ADR 003. Update the ERD wording to match this rule. |
| D12 | Row locking | Update/cancel/soft-delete load the event with `SELECT ... FOR UPDATE` to serialize concurrent edits and future booking operations. |
| D13 | Error shape | Existing FastAPI `{"detail": "..."}` shape; no global `{detail, code, status_code}` envelope yet. |
| D14 | Past dates | No past-date restriction on create/update; Day 3 booking enforces that an event is not in the past. This allows backfilling historical/draft events. |

### PATCH null semantics

- Omitted fields are unchanged.
- `category_id: null` clears the category.
- Explicit `null` for `title`, `description`, `venue`, `starts_at`, `price`, `total_tickets`, or `status` is invalid and returns `422`; these database fields are non-nullable.
- `tag_ids: null` is invalid and returns `422`. Use `tag_ids: []` to clear all tags.
- Reject invalid nulls during request validation, before service code can assign them to ORM fields.

---

## 3. Affected Files & Components

### New files

| Path | Purpose |
| :--- | :--- |
| `backend/app/schemas/events.py` | Pydantic v2 request/response schemas for events, categories, and tags. |
| `backend/app/events/service.py` | Business logic: catalogue query, CRUD, status transitions, taxonomy, audit. |
| `backend/app/events/router.py` | Thin `/events`, `/categories`, and `/tags` endpoints. |
| `backend/app/events/dependencies.py` | `get_managed_event` dependency: row lock + role/ownership enforcement (IDOR-safe). |
| `backend/tests/test_events/__init__.py` | Test package marker. |
| `backend/tests/test_events/conftest.py` | Event/category/tag fixtures and payload helpers with cleanup. |
| `backend/tests/test_events/test_events_service.py` | Service-level tests (invariants, transitions, filters). |
| `backend/tests/test_events/test_events_endpoints.py` | Endpoint/RBAC/IDOR/audit tests. |
| `backend/tests/test_events/test_events_catalogue.py` | Filtering, sorting, and pagination tests. |
| `backend/tests/test_events/test_categories_tags.py` | Taxonomy endpoint tests. |

### Modified files

| Path | Change |
| :--- | :--- |
| `backend/app/schemas/__init__.py` | Export the new event/category/tag schemas. |
| `backend/app/main.py` | `app.include_router(events_router, prefix=settings.API_V1_STR)`. |
| `docs/API_CONTRACT.md` | Rewrite §3 with full request/response schemas, filters, sorting, status rules, and the taxonomy endpoints. |
| `docs/ERD.md` | Clarify that audit rows are inserted atomically in the same transaction as the audited change; external side effects happen after commit. |

### Not touched

- `backend/app/models/**`, `backend/alembic/**` — no schema changes; the initial migration already contains all required tables, constraints, and indexes. Confirm with `alembic check` during verification.
- `backend/app/bookings/**`, `reviews/**`, `notifications/**`, `tasks/**`, `realtime/**` — no changes.
- `frontend/**` — no frontend work in this iteration.

---

## 4. API Design

All endpoints live under `/api/v1` and accept/return JSON. Public endpoints require no auth; write endpoints require `Authorization: Bearer <access_token>`.

### 4.1 `GET /events` — public

Query parameters:

| Parameter | Type | Rules |
| :--- | :--- | :--- |
| `page` | int | ≥ 1, default 1 |
| `size` | int | 1–100, default 20 |
| `search` | str | optional; case-insensitive `ILIKE` on `title` |
| `category` | str | optional; category slug |
| `tag` | str | optional; repeatable; tag slug; OR semantics |
| `date_from` | datetime | optional; `starts_at >= date_from` |
| `date_to` | datetime | optional; `starts_at <= date_to` |
| `price_min` | decimal | optional; ≥ 0 |
| `price_max` | decimal | optional; ≥ 0 |
| `sort` | enum | `date` (default) or `price` |
| `order` | enum | `asc` (default) or `desc` |

Behavior:

- Only `status = published` and `deleted_at IS NULL` rows are returned.
- `date_from > date_to` or `price_min > price_max` → `422`.
- Unknown category/tag slugs return an empty page (not `404`).
- Results are ordered by the selected sort column, then `id` (stable pagination).

Response `200`:

```json
{
  "items": [ { "...EventRead..." } ],
  "total": 123,
  "page": 1,
  "size": 20
}
```

### 4.2 `GET /events/{id}` — public

Response `200`: `EventDetailRead` (same shape as `EventRead` in this iteration; reviews summary is added in Day 4).

- `404` if the event does not exist, is soft-deleted, or is not `published`.

### 4.3 `POST /events` — admin / organizer

Request:

```json
{
  "category_id": "9f1c2b3e-0000-4000-8000-000000000000",
  "title": "PyCon 2026",
  "description": "Annual Python conference",
  "venue": "Convention Center",
  "starts_at": "2026-12-01T18:00:00Z",
  "price": "199.00",
  "total_tickets": 500,
  "status": "draft",
  "tag_ids": ["9f1c2b3e-0000-4000-8000-000000000001"]
}
```

Rules:

- `title`: 1–255 chars; `description`: ≥ 1 char; `venue`: 1–255 chars.
- `price`: decimal ≥ 0, `NUMERIC(10,2)`.
- `total_tickets`: integer ≥ 0.
- `status`: `draft` (default) or `published`.
- `category_id` must reference an existing category when provided; otherwise `422`.
- Every `tag_ids` entry must reference an existing tag; otherwise `422`.
- `organizer_id` is taken from the authenticated user.
- `tickets_available` is set to `total_tickets`.
- Audit action `EVENT_CREATE`.

Responses:

| Status | Body |
| :--- | :--- |
| `201` | `EventRead` |
| `401` | `{"detail": "Authentication credentials were not provided."}` |
| `403` | `{"detail": "Access forbidden: required role is one of ['admin', 'organizer']."}` |
| `422` | Pydantic validation errors (invalid UUIDs, negative price/tickets, missing category/tag, bad status) |

### 4.4 `PATCH /events/{id}` — admin any / organizer owner

Request (`EventUpdate`, all fields optional):

```json
{
  "category_id": null,
  "title": "PyCon 2026 (Updated)",
  "description": "Updated description",
  "venue": "Convention Center",
  "starts_at": "2026-12-02T18:00:00Z",
  "price": "149.00",
  "total_tickets": 600,
  "status": "published",
  "tag_ids": []
}
```

Rules:

- Only fields present in the request (`model_fields_set`) are updated; explicit `category_id: null` clears the category.
- Explicit `null` for non-nullable event fields or `tag_ids` is rejected with `422`; `tag_ids: []` clears tags.
- Field edits require the current status to be `draft` or `published` (D3).
- `total_tickets` follows D4.
- `status` follows the transition map in D2; invalid → `409`.
- `tag_ids` replaces the complete tag set; empty list clears tags.
- The event row is locked `FOR UPDATE` before validation.
- Audit action: `EVENT_CANCEL` when the transition target is `cancelled`; otherwise `EVENT_UPDATE`. The audit metadata records the changed fields and the old/new status.

Responses:

| Status | Body |
| :--- | :--- |
| `200` | `EventRead` |
| `401` | Missing/invalid access token |
| `403` | Attendee, or organizer who does not own the event (IDOR) |
| `404` | Event missing or soft-deleted |
| `409` | Invalid status transition, edit on a terminal event, or `total_tickets < sold` |
| `422` | Validation errors (bad UUIDs, negative values, nonexistent category/tag) |

### 4.5 `DELETE /events/{id}` — admin any / organizer owner

Behavior:

- Sets `deleted_at = now()` (soft delete); the row is never hard-deleted.
- The event disappears from `GET /events` and `GET /events/{id}`.
- Audit action `EVENT_DELETE`.

Responses: `204 No Content`; `401` unauthenticated; `403` non-owner organizer/attendee; `404` missing or already deleted.

### 4.6 `GET /categories` — public

Response `200`: `list[CategoryRead]` ordered by `name`. No pagination (small taxonomy).

### 4.7 `POST /categories` — admin

Request: `{ "name": "Conferences", "slug": "conferences", "description": "..." }` (`slug` optional).
Behavior: auto-generates a unique slug from `name` when omitted; duplicate slug → `409`.
Responses: `201 CategoryRead`; `403` non-admin; `409` duplicate slug; `422` validation.

### 4.8 `GET /tags` — public

Response `200`: `list[TagRead]` ordered by `name`.

### 4.9 `POST /tags` — admin

Request: `{ "name": "python", "slug": "python" }` (`slug` optional).
Behavior: auto-generates a unique slug when omitted; duplicate slug → `409`.
Responses: `201 TagRead`; `403` non-admin; `409` duplicate slug; `422` validation.

---

## 5. Schema Definitions (`backend/app/schemas/events.py`)

```text
CategoryRead
  id: uuid.UUID
  name: str
  slug: str
  description: str | None
  created_at: datetime
  updated_at: datetime

CategoryCreate
  name: str (1..100)
  slug: str | None (1..120)      # auto-generated when omitted
  description: str | None

TagRead
  id: uuid.UUID
  name: str
  slug: str
  created_at: datetime
  updated_at: datetime

TagCreate
  name: str (1..50)
  slug: str | None (1..60)       # auto-generated when omitted

EventBase
  title: str (1..255)
  description: str (min_length=1)
  venue: str (1..255)
  starts_at: datetime
  price: Decimal (ge=0, max_digits=10, decimal_places=2)
  total_tickets: int (ge=0)

EventCreate(EventBase)
  category_id: uuid.UUID | None = None
  status: EventStatus = EventStatus.DRAFT
  tag_ids: list[uuid.UUID] = []

EventUpdate
  category_id: uuid.UUID | None = None   # explicit null clears
  title: str (optional; 1..255; explicit null rejected)
  description: str (optional; min_length=1; explicit null rejected)
  venue: str (optional; 1..255; explicit null rejected)
  starts_at: datetime (optional; explicit null rejected)
  price: Decimal (optional; ge=0; explicit null rejected)
  total_tickets: int (optional; ge=0; explicit null rejected)
  status: EventStatus (optional; explicit null rejected)
  tag_ids: list[uuid.UUID] (optional; explicit null rejected; [] clears)
  # Omitted fields remain unchanged. category_id is the only nullable
  # patch field; explicit null clears it.

CategoryRef
  id: uuid.UUID
  name: str
  slug: str

TagRef
  id: uuid.UUID
  name: str
  slug: str

OrganizerRef
  id: uuid.UUID
  full_name: str

EventRead
  id: uuid.UUID
  organizer_id: uuid.UUID
  organizer: OrganizerRef
  category_id: uuid.UUID | None
  category: CategoryRef | None
  title: str
  description: str
  venue: str
  starts_at: datetime
  price: Decimal                 # JSON string under Pydantic v2
  total_tickets: int
  tickets_available: int
  status: EventStatus
  tags: list[TagRef]
  created_at: datetime
  updated_at: datetime

EventDetailRead(EventRead)        # reviews summary added in Day 4

EventListResponse
  items: list[EventRead]
  total: int
  page: int
  size: int
```

All schemas use `model_config = ConfigDict(from_attributes=True)`. No password/hash/token fields are ever serialized.

---

## 6. Service, Dependency & Router Changes

### 6.1 `backend/app/events/service.py`

| Function | Behavior |
| :--- | :--- |
| `list_events(db, *, page, size, search, category, tags, date_from, date_to, price_min, price_max, sort, order) -> tuple[list[Event], int]` | Builds one filtered base query (`published`, `deleted_at IS NULL`), applies all filters, returns `(items, total)`. Uses `selectinload` for `category`, `tags`, and `organizer` to avoid N+1. |
| `get_event_detail(db, event_id) -> Event` | Published, non-deleted event with eager-loaded relations; `404` otherwise. |
| `get_event_with_lock(db, event_id) -> Event` | `SELECT ... FOR UPDATE` on a non-deleted event; `404` otherwise. |
| `create_event(db, payload, organizer_id) -> Event` | Validates category/tags, sets `tickets_available = total_tickets`, inserts, writes `EVENT_CREATE` audit, commits, reloads relations. |
| `update_event(db, event, payload, actor_id) -> Event` | Applies only `model_fields_set` fields, enforces D3/D4 and the transition map, replaces tags, writes `EVENT_UPDATE` or `EVENT_CANCEL` audit, commits. |
| `soft_delete_event(db, event, actor_id) -> None` | Sets `deleted_at`, writes `EVENT_DELETE` audit, commits. |
| `list_categories(db) -> list[Category]` | Ordered by `name`. |
| `create_category(db, payload, actor_id) -> Category` | Auto-slugs, catches `IntegrityError` → `409`, writes audit. |
| `list_tags(db) -> list[Tag]` | Ordered by `name`. |
| `create_tag(db, payload, actor_id) -> Tag` | Auto-slugs, catches `IntegrityError` → `409`, writes audit. |
| `_validate_category_and_tags(db, category_id, tag_ids)` | Raises `422` when a referenced UUID does not exist. |
| `_slugify(name) -> str` | Stdlib-only slug generation (`unicodedata` + `re`), lowercased, hyphen-separated. |
| `_event_audit(db, action, event, actor_id, metadata)` | Adds an `AuditLog` row to the current transaction. |

Transaction rule: each write operation uses one transaction for domain changes and its audit row. Commit once; roll back both on failure. No Celery/Redis/WebSocket/email side effects are dispatched in this iteration. Future external side effects must run after a successful commit (D11 / ADR 003).

### 6.2 `backend/app/events/dependencies.py`

```text
get_managed_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Event
```

- Loads the event with `SELECT ... FOR UPDATE`; `404` if missing or soft-deleted.
- Enforces admin-any / organizer-owner via the existing `ownership_check(event.organizer_id, current_user, allow_admin=True)`; `403` otherwise.
- Router-level role gating uses `require_role(UserRole.ADMIN, UserRole.ORGANIZER)`.

This keeps routers thin and prevents IDOR without ad-hoc checks in route bodies.

### 6.3 `backend/app/events/router.py`

```text
router = APIRouter(tags=["Events"])

GET    /events              -> 200 EventListResponse (public)
GET    /events/{id}         -> 200 EventDetailRead   (public)
POST   /events              -> 201 EventRead          (admin/organizer)
PATCH  /events/{id}         -> 200 EventRead          (managed event)
DELETE /events/{id}         -> 204                  (managed event)
GET    /categories          -> 200 list[CategoryRead]
POST   /categories          -> 201 CategoryRead      (admin)
GET    /tags                -> 200 list[TagRead]
POST   /tags                -> 201 TagRead           (admin)
```

The router only validates HTTP input and maps service exceptions to status codes. All business logic stays in `service.py`.

### 6.4 `backend/app/main.py`

```python
from app.events.router import router as events_router
...
app.include_router(events_router, prefix=settings.API_V1_STR)
```

No duplicate/unprefixed mounting.

---

## 7. Tests

### 7.1 Fixtures (`backend/tests/test_events/conftest.py`)

- `category` — persisted `Category`.
- `tags` — two persisted `Tag` rows.
- `event_factory` / `published_event` / `draft_event` — helpers that create events for a given organizer with cleanup.
- `event_payload(...)` — valid `POST /events` payload builder.
- **Cleanup note**: `events.organizer_id` is `ON DELETE RESTRICT`, and the shared `organizer_user` fixture deletes its user on teardown. Event fixtures must be finalized before the user fixtures (or tests must delete events explicitly in `try/finally`) so user teardown never violates the FK.

### 7.2 Service tests (`test_events_service.py`)

- Create sets `tickets_available == total_tickets`.
- Create rejects nonexistent `category_id` / `tag_ids` (`422`).
- Update recalculates `tickets_available` when `total_tickets` changes.
- Update rejects `total_tickets < sold` (`409`).
- Status transition matrix: every valid transition succeeds; every invalid transition raises `409`.
- Edit on `cancelled` / `completed` is rejected.
- Soft delete excludes the event from list/detail queries.
- Catalogue filters: category, tag (including multiple tags), date range, price range, title search, sorting (`date`/`price`, `asc`/`desc`), pagination (`page`/`size`/`total`), published-only, soft-deleted excluded.
- Category/tag slug auto-generation and duplicate-slug handling.

### 7.3 Endpoint tests (`test_events_endpoints.py`)

- RBAC matrix for `POST`/`PATCH`/`DELETE`: admin succeeds; owning organizer succeeds; non-owning organizer `403`; attendee `403`; unauthenticated `401`.
- IDOR: organizer B cannot patch/delete organizer A's event.
- `PATCH` transitions: `draft→published` `200`; `published→cancelled` `200`; `cancelled→published` `409`; `draft→completed` `409`.
- `DELETE` soft-deletes: subsequent `GET /events/{id}` `404`; list excludes it; the DB row still exists with `deleted_at` set.
- Audit rows exist for create/update/cancel/delete with the correct `action`, `actor_id`, and `entity_id`.
- Validation: negative price `422`; negative `total_tickets` `422`; empty title `422`; malformed UUID `422`; nonexistent category/tag `422`.
- PATCH semantics: omitted fields stay unchanged; `category_id: null` clears the category; explicit null for each non-nullable field and `tag_ids` returns `422`; `tag_ids: []` clears tags.
- `GET /events` and `GET /events/{id}` work without auth and never leak draft/cancelled/completed/soft-deleted events.

### 7.4 Catalogue tests (`test_events_catalogue.py`)

- Filter combinations (category + tag + date range + price range + search).
- Sorting and ordering, including tie-break stability.
- Pagination envelope and boundary values (`page=1`, `size=1`, `size=100`, out-of-range page returns empty `items` with correct `total`).
- Invalid range (`date_from > date_to`, `price_min > price_max`) → `422`.

### 7.5 Taxonomy tests (`test_categories_tags.py`)

- `GET /categories` and `GET /tags` are public.
- `POST` as admin → `201`; as organizer/attendee → `403`; unauthenticated → `401`.
- Duplicate slug → `409`; omitted slug is auto-generated.
- Invalid name length → `422`.

### 7.6 Full flow / regression

- Existing `tests/test_auth`, `tests/test_users`, `tests/test_schema`, and `tests/test_health` stay green.
- Full suite: `pytest -q`.

---

## 8. Verification Commands

```bash
cd backend
./.venv/bin/ruff check app tests
./.venv/bin/ruff format --check app tests
./.venv/bin/python -m pytest tests/test_events -q
./.venv/bin/python -m pytest -q
./.venv/bin/alembic check
```

Manual smoke checks (after implementation):

```bash
# Create a category + tag (admin token required)
curl -X POST http://localhost:8000/api/v1/categories \
  -H "Authorization: Bearer <admin_access>" -H 'Content-Type: application/json' \
  -d '{"name":"Conferences"}'

curl -X POST http://localhost:8000/api/v1/tags \
  -H "Authorization: Bearer <admin_access>" -H 'Content-Type: application/json' \
  -d '{"name":"python"}'

# Create an event (organizer token)
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer <organizer_access>" -H 'Content-Type: application/json' \
  -d '{"title":"PyCon 2026","description":"Annual Python conference","venue":"Convention Center","starts_at":"2026-12-01T18:00:00Z","price":"199.00","total_tickets":500,"status":"published","category_id":"<category_id>","tag_ids":["<tag_id>"]}'

# Catalogue with filters
curl "http://localhost:8000/api/v1/events?category=conferences&tag=python&price_min=50&price_max=250&sort=price&order=asc&page=1&size=20"

# Publish / cancel transition
curl -X PATCH http://localhost:8000/api/v1/events/<event_id> \
  -H "Authorization: Bearer <organizer_access>" -H 'Content-Type: application/json' \
  -d '{"status":"cancelled"}'

# Soft delete
curl -X DELETE http://localhost:8000/api/v1/events/<event_id> \
  -H "Authorization: Bearer <organizer_access>"
```

Acceptance criteria:

- All commands above pass; the full suite remains green.
- No event is returned unless it is published and not soft-deleted.
- `tickets_available == total_tickets` on create.
- Organizers can only modify their own events; admins can modify any.
- Every status transition follows D2; invalid transitions return `409`.
- Audit rows exist for create/update/cancel/delete.
- No notifications, Celery jobs, or WebSocket messages are emitted.

---

## 9. Known Limitations / Follow-ups

1. **Cancel notifications**: explicitly deferred to Day 4. The service transition is the single hook point; Celery/WS dispatch must run after commit per ADR 003.
2. **Reviews summary**: `GET /events/{id}` returns the event payload only; the reviews summary is added in Day 4.
3. **Taxonomy management**: category/tag update and delete are not implemented; only admin create and public read.
4. **Admin event listing**: no admin-only endpoint to list draft/cancelled/completed events; the organizer dashboard (Day 5) will need one.
5. **Audit timing**: resolved by D11. Audit rows commit atomically with the event change; external side effects run after commit. `docs/ERD.md` is included in this task to align the canonical wording.
6. **Completed event visibility**: `GET /events/{id}` hides completed events (D9). Revisit if public completed-event pages are required.
7. **Error envelope**: the contract's `{detail, code, status_code}` shape remains a cross-cutting follow-up.
8. **Rate limiting**: no brute-force/abuse protection on the new endpoints.
9. **Frontend integration**: `frontend/` is still a scaffold; generated API types cannot be consumed until the Next.js app exists.
10. **No DB migration**: the existing initial migration already covers all tables, constraints, and indexes used here.

---

## 10. Estimated Time

| Work | Estimate |
| :--- | :--- |
| Schemas (events, categories, tags) | 45 min |
| Service layer (catalogue, CRUD, transitions, taxonomy) | 120 min |
| Dependencies + router + `main.py` wiring | 40 min |
| API contract update | 30 min |
| Test fixtures + service tests | 75 min |
| Endpoint / catalogue / taxonomy tests | 105 min |
| Full verification / fixes | 35 min |
| **Total** | **~7.5 hours** |

The decisions and request semantics in this proposal are the implementation target. Keep `docs/API_CONTRACT.md`, `docs/ERD.md`, schemas, services, and tests aligned with them.
