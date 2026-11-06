# Architectural Decision Records (ADRs)

## ADR 001: Booking Concurrency & Race Condition Prevention
* **Date**: Day 0
* **Status**: Accepted
* **Context**: Multiple users may attempt to book the last available tickets for a popular event simultaneously. A simple read-then-write approach (`if event.available_tickets >= count: event.available_tickets -= count`) leads to overselling under concurrency.
* **Decision**: 
  - Execute booking and cancellation operations within an atomic PostgreSQL transaction.
  - Acquire an exclusive row-level lock on the event record: `SELECT * FROM events WHERE id = :event_id FOR UPDATE`.
  - Add a database-level `CHECK (available_tickets >= 0)` constraint as an ultimate safety backstop.
  - Test with a 50-concurrent-request real Postgres integration test.
* **Consequences**: Ensures zero overselling. Requires PostgreSQL (cannot use SQLite in production or concurrency testing).

---

## ADR 002: Authentication & Token Lifecycle
* **Date**: Day 0
* **Status**: Accepted
* **Context**: Need secure user session management without session state in the application server.
* **Decision**:
  - Passwords hashed with `Argon2` (`argon2-cffi`).
  - Short-lived JWT access tokens (15-minute expiration) passed in headers.
  - Long-lived refresh tokens (7-day expiration) stored in the database in hashed form (`SHA-256`).
  - Refresh token rotation: each refresh issues a new refresh token and revokes the previous one.
  - Logout explicitly marks the refresh token record as revoked.
* **Consequences**: Safe against token theft replay attacks; allows selective logout.

---

## ADR 003: Post-Commit Asynchronous Side Effects
* **Date**: Day 0
* **Status**: Accepted
* **Context**: Booking actions require notification emails, Celery jobs, and WebSocket broadcasts.
* **Decision**:
  - Never trigger external networks (SMTP, Redis pub/sub) inside the uncommitted SQL transaction.
  - Dispatch tasks via FastAPI background tasks or Celery immediately *after* `db.commit()` succeeds.
* **Consequences**: If the database transaction rolls back, no false confirmation emails or ghost WebSocket decrements are dispatched.
