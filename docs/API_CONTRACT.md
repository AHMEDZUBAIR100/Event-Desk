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
| `GET` | `/events` | None | List published events with pagination (`page`, `size`, `search`, `status`). |
| `GET` | `/events/{id}` | None | Get detailed event information including available tickets and reviews summary. |
| `POST` | `/events` | Organizer / Admin | Create a new event. |
| `PATCH` | `/events/{id}` | Organizer (Owner) / Admin | Update event details. (Checks organizer ownership). |
| `DELETE`| `/events/{id}` | Organizer (Owner) / Admin | Soft-delete an event. |

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
