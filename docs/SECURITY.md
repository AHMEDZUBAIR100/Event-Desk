# Security Architecture & Checklist

## 1. Authentication & Session Management
- **Password Hashing**: `argon2-cffi` with standard memory/time cost parameters.
- **Access Tokens**: Short-lived (15 minutes), signed using `HS256` (or `RS256`), containing `sub` (user_id) and `role`.
- **Refresh Tokens**: Long-lived (7 days), stored in database as a SHA-256 hash. Replay detection on rotation.
- **Revocation**: Logging out revokes the refresh token immediately in the database.

## 2. Authorization & RBAC
- Reusable FastAPI dependencies (`get_current_active_user`, `require_role`).
- Multi-tenancy / Ownership checks: Organizers may only edit/delete events where `event.organizer_id == current_user.id`.
- Attendees cannot access organizer dashboards or create events.

## 3. Database & SQL Security
- Exclusively async SQLAlchemy 2.0 ORM with parameterized queries (no raw string formatting).
- Soft deletes: Every query filtering users, events, and bookings must include `.where(Model.deleted_at.is_(None))`.
- Row-level lock (`SELECT ... FOR UPDATE`) used on all ticket stock decrementing/incrementing transactions.

## 4. Input Validation & Data Sanitization
- Strict Pydantic v2 schemas with constrained types (`EmailStr`, `conint`, `constr`).
- Frontend validation using Zod mirrors backend constraints.
- Sensitive data excluded from API responses (passwords, token hashes).
