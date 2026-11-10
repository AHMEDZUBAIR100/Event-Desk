# API Contract Specification

All endpoints are prefixed with `/api/v1`. Authentication uses `Bearer <access_token>`.

---

## 1. Authentication (`/api/v1/auth`)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | None | Register an `attendee` or `organizer`. Admin self-registration is rejected. Returns `201` with `UserRead`. |
| `POST` | `/auth/login` | None | Authenticate with email/password; returns `access_token`, `refresh_token`, `token_type`, `expires_in`, and the user profile. |
| `POST` | `/auth/refresh` | Valid refresh token (body) | Rotates the refresh token and issues a new `access_token` and `refresh_token`. |
| `POST` | `/auth/logout` | Bearer access token | Revokes the refresh token supplied in the body. Returns `204`. |
| `GET` | `/auth/me` | Authenticated | Deferred. Use `GET /users/me` as the canonical profile endpoint. |

### 1.1 Token response (`AuthResponse`)

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<opaque-random-token>",
  "token_type": "bearer",
  "expires_in": 900,
  "user": { "...UserRead..." }
}
```

### 1.2 `POST /auth/register`

Request:

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "full_name": "Jane Doe",
  "role": "attendee"
}
```

- `password` is 8–128 characters; `full_name` is 1–255 characters.
- `role` defaults to `attendee`; only `attendee` and `organizer` are accepted.
- Emails are normalized to lowercase and looked up case-insensitively.
- A soft-deleted account's email may be reused.
- Responses: `201` `UserRead`, `403` admin self-registration, `409` duplicate active email, `422` validation error.

### 1.3 `POST /auth/login`

Request:

```json
{ "email": "user@example.com", "password": "StrongPass123!" }
```

- Returns `200` with `AuthResponse`.
- Wrong password, unknown email, inactive user, and soft-deleted user all return the same `401` `{"detail": "Invalid email or password."}`.

### 1.4 `POST /auth/refresh`

Request:

```json
{ "refresh_token": "<opaque-random-token>" }
```

- Returns `200` with `AuthResponse`.
- The presented token is revoked atomically and replaced; reuse of the old token returns `401`.
- Missing, malformed, expired, revoked, or inactive/deleted-owner tokens return `401`.

### 1.5 `POST /auth/logout`

Headers: `Authorization: Bearer <access_token>`

Request:

```json
{ "refresh_token": "<opaque-random-token>" }
```

- Revokes the token only when it belongs to the authenticated user.
- Always returns `204` (idempotent; missing/foreign/already-revoked tokens are ignored).
- Missing or invalid access token returns `401`.

---

## 2. User Management (`/api/v1/users` & `/api/v1/admin/users`)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/users/me` | Authenticated | Returns current authenticated user profile (`id`, `email`, `full_name`, `role`, `is_active`, `created_at`, `updated_at`, `deleted_at`). |
| `PATCH` | `/users/me` | Authenticated | Change password (`old_password`, `new_password` ≥ 8 chars). Validates current password, rejects identical new password, and verifies ownership. |
| `GET` | `/admin/users` | Admin | List users with pagination (`limit`, `offset`) and `include_deleted` flag (defaults to false, excluding soft-deleted records). |
| `PATCH` | `/admin/users/{id}` | Admin | Update user `role`, toggle `is_active`, or soft-delete/restore (`deleted_at`, `is_deleted`). Deactivation or soft-delete automatically revokes all active refresh tokens. Records audit trail. |

---

## 3. Events (`/api/v1/events`)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/events` | None | Public catalogue of published, non-deleted events with filters, sorting, and pagination. |
| `GET` | `/events/{id}` | None | Get a published, non-deleted event with category, tags, organizer summary, and live availability. |
| `POST` | `/events` | Organizer / Admin | Create an event. `tickets_available` is initialized to `total_tickets`. |
| `PATCH` | `/events/{id}` | Organizer (Owner) / Admin | Partial update and status transitions. Organizers may only modify their own events. |
| `DELETE` | `/events/{id}` | Organizer (Owner) / Admin | Soft-delete an event (`deleted_at` is set; the row is retained). |

### 3.1 `GET /events` — query parameters

| Parameter | Type | Rules |
| :--- | :--- | :--- |
| `page` | int | ≥ 1, default `1`. |
| `size` | int | 1–100, default `20`. |
| `search` | str | Case-insensitive `ILIKE` match on `title`. |
| `category` | str | Category slug. Unknown slug returns an empty page. |
| `tag` | str | Tag slug; repeatable. Multiple tags use **OR** semantics. |
| `date_from` | datetime | `starts_at >= date_from` (ISO 8601). |
| `date_to` | datetime | `starts_at <= date_to` (ISO 8601). |
| `price_min` | decimal | ≥ 0. |
| `price_max` | decimal | ≥ 0. |
| `sort` | enum | `date` (default) or `price`. |
| `order` | enum | `asc` (default) or `desc`. |

Behavior:

- Only `status = published` and `deleted_at IS NULL` events are returned.
- `date_from > date_to` or `price_min > price_max` → `422`.
- Unknown category/tag slugs return an empty page, not `404`.
- Tie-break on `id` for deterministic pagination.

Response `200`:

```json
{
  "items": [ { "...EventRead..." } ],
  "total": 123,
  "page": 1,
  "size": 20
}
```

### 3.2 `GET /events/{id}`

- Returns `200` `EventDetailRead` (same shape as `EventRead` until the Day 4 reviews summary).
- Returns `404` when the event is missing, soft-deleted, or not `published`.

### 3.3 `POST /events`

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

- `title`: 1–255 chars; `description`: ≥ 1 char; `venue`: 1–255 chars.
- `price`: decimal ≥ 0 (`NUMERIC(10,2)`); `total_tickets`: integer ≥ 0.
- `status`: `draft` (default) or `published` on creation; other values → `422`.
- `category_id`, when provided, must reference an existing category; every `tag_ids` entry must reference an existing tag; otherwise `422`.
- `organizer_id` is taken from the authenticated user.
- Responses: `201` `EventRead`, `401` unauthenticated, `403` attendee, `422` validation error.

### 3.4 `PATCH /events/{id}`

Request (`EventUpdate`; all fields optional):

```json
{
  "category_id": null,
  "title": "PyCon 2026 (Updated)",
  "price": "149.00",
  "total_tickets": 600,
  "status": "published",
  "tag_ids": []
}
```

- Omitted fields remain unchanged.
- `category_id: null` clears the category; `tag_ids: []` clears all tags.
- Explicit `null` for `title`, `description`, `venue`, `starts_at`, `price`, `total_tickets`, `status`, or `tag_ids` → `422`.
- Field edits are allowed only while the event is `draft` or `published`; editing `cancelled`/`completed` → `409`.
- `total_tickets` may not drop below the number already sold (`total_tickets - tickets_available`); violation → `409`. Availability is recalculated as `new_total - sold`.
- `tag_ids` replaces the complete tag set.
- The event row is locked with `SELECT ... FOR UPDATE` before validation.
- Responses: `200` `EventRead`, `401`, `403` (attendee or non-owner organizer), `404`, `409` (invalid transition/terminal edit/ticket count), `422`.

### 3.5 Status machine

| Current | Allowed targets |
| :--- | :--- |
| `draft` | `published`, `cancelled` |
| `published` | `cancelled`, `completed` |
| `cancelled` | none (terminal) |
| `completed` | none (terminal) |

Invalid transitions return `409`. A PATCH containing only the event's current status is an idempotent no-op: it returns `200` without changing `updated_at`, writing an audit row, or committing. This also applies to `cancelled` and `completed` events; any actual field edit or real transition on a terminal event still returns `409`.

### 3.6 `DELETE /events/{id}`

- Sets `deleted_at`; the row is never hard-deleted and disappears from the catalogue and detail endpoints.
- Responses: `204`; `401` unauthenticated; `403` non-owner organizer/attendee; `404` missing or already deleted.

### 3.7 Event response shape (`EventRead`)

```json
{
  "id": "uuid",
  "organizer_id": "uuid",
  "organizer": { "id": "uuid", "full_name": "Jane Doe" },
  "category_id": "uuid | null",
  "category": { "id": "uuid", "name": "Conferences", "slug": "conferences" },
  "title": "PyCon 2026",
  "description": "Annual Python conference",
  "venue": "Convention Center",
  "starts_at": "2026-12-01T18:00:00Z",
  "price": "199.00",
  "total_tickets": 500,
  "tickets_available": 500,
  "status": "draft",
  "tags": [{ "id": "uuid", "name": "python", "slug": "python" }],
  "created_at": "2026-11-10T12:00:00Z",
  "updated_at": "2026-11-10T12:00:00Z"
}
```

`price` is a decimal serialized as a JSON string. `deleted_at` is never exposed.

### 3.8 Categories & tags

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/categories` | None | List categories ordered by name. |
| `POST` | `/categories` | Admin | Create a category. Body: `name` (1–100), optional `slug` (1–120), optional `description`. |
| `GET` | `/tags` | None | List tags ordered by name. |
| `POST` | `/tags` | Admin | Create a tag. Body: `name` (1–50), optional `slug` (1–60). |

- When `slug` is omitted it is generated from `name`; generated collisions receive a numeric suffix. If concurrent creates race for the same generated slug, the losing request retries with the next available suffix (up to 10 attempts); both requests normally succeed with distinct slugs.
- An explicitly supplied duplicate slug → `409`; explicit slugs are never rewritten.
- Non-admin writes → `403`; unauthenticated writes → `401`.
- Taxonomy update/delete are not implemented in this iteration.

### 3.9 Audit actions

`EVENT_CREATE`, `EVENT_UPDATE`, `EVENT_CANCEL`, `EVENT_DELETE`, `CATEGORY_CREATE`, and `TAG_CREATE` are written to `audit_logs` in the same transaction as the change.

---

## 4. Bookings (`/api/v1/bookings`)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/bookings` | Authenticated (Attendee) | Book tickets (`event_id`, `ticket_count`). Concurrency safe. |
| `GET` | `/bookings/me` | Authenticated | List current user's bookings. |
| `GET` | `/bookings/{id}` | Authenticated | View booking details (owner or admin). |
| `POST` | `/bookings/{id}/cancel` | Authenticated | Cancel booking & release tickets back to pool. |

---

## 5. Reviews (`/api/v1/reviews`)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/events/{id}/reviews` | Attendee (Booked) | Submit a review (1-5 stars + text) for an attended event. |
| `GET` | `/events/{id}/reviews` | None | List reviews for an event. |

---

## 6. Notifications & WebSockets

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/notifications` | Authenticated | List user notifications. |
| `PATCH`| `/notifications/{id}/read` | Authenticated | Mark notification as read. |
| `WS` | `/ws/events/{id}` | None / Token | WebSocket channel for real-time ticket availability count. |
| `WS` | `/ws/notifications` | Authenticated | Real-time user alert channel. |

---

## 7. Standard Error Format

Target envelope:
```json
{
  "detail": "Error description message",
  "code": "SPECIFIC_ERROR_CODE",
  "status_code": 400
}
```

**Implementation note (current):** existing endpoints, including `/auth/*`, return FastAPI's
standard `{"detail": "Error description message"}` shape. The `code`/`status_code` envelope is
a planned cross-cutting follow-up so it can be applied consistently to every route.
