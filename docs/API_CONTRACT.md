# API Contract Specification

All endpoints are prefixed with `/api/v1`. Authentication uses `Bearer <access_token>`.

---

## 1. Authentication (`/api/v1/auth`)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | None | Register a new user (`email`, `password`, `full_name`, `role`). |
| `POST` | `/auth/login` | None | Authenticate user; returns `access_token`, `refresh_token`, and user profile. |
| `POST` | `/auth/refresh` | Refresh Token | Rotates refresh token and issues a new `access_token` and `refresh_token`. |
| `POST` | `/auth/logout` | Authenticated | Revokes current refresh token. |
| `GET` | `/auth/me` | Authenticated | Returns currently authenticated user profile. |

---

## 2. Events (`/api/v1/events`)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/events` | None | List published events with pagination (`page`, `size`, `search`, `status`). |
| `GET` | `/events/{id}` | None | Get detailed event information including available tickets and reviews summary. |
| `POST` | `/events` | Organizer / Admin | Create a new event. |
| `PATCH` | `/events/{id}` | Organizer (Owner) / Admin | Update event details. (Checks organizer ownership). |
| `DELETE`| `/events/{id}` | Organizer (Owner) / Admin | Soft-delete an event. |

---

## 3. Bookings (`/api/v1/bookings`)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/bookings` | Authenticated (Attendee) | Book tickets (`event_id`, `ticket_count`). Concurrency safe. |
| `GET` | `/bookings/me` | Authenticated | List current user's bookings. |
| `GET` | `/bookings/{id}` | Authenticated | View booking details (owner or admin). |
| `POST` | `/bookings/{id}/cancel` | Authenticated | Cancel booking & release tickets back to pool. |

---

## 4. Reviews (`/api/v1/reviews`)

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/events/{id}/reviews` | Attendee (Booked) | Submit a review (1-5 stars + text) for an attended event. |
| `GET` | `/events/{id}/reviews` | None | List reviews for an event. |

---

## 5. Notifications & WebSockets

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/notifications` | Authenticated | List user notifications. |
| `PATCH`| `/notifications/{id}/read` | Authenticated | Mark notification as read. |
| `WS` | `/ws/events/{id}` | None / Token | WebSocket channel for real-time ticket availability count. |
| `WS` | `/ws/notifications` | Authenticated | Real-time user alert channel. |

---

## 6. Standard Error Format

All error responses return:
```json
{
  "detail": "Error description message",
  "code": "SPECIFIC_ERROR_CODE",
  "status_code": 400
}
```
