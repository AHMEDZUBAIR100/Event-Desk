# Testing Strategy & Guidelines

## 1. Test Architecture
- **Framework**: `pytest`, `pytest-asyncio`, `httpx` (AsyncClient).
- **Database**: All integration tests run against a real PostgreSQL test instance (never SQLite).

## 2. Concurrency Test Requirements (Day 3 Gate)
To prove zero overselling:
- Create an event with a limited ticket capacity (e.g., 20 tickets available).
- Launch 50 concurrent booking requests simultaneously using `asyncio.gather` across multiple tasks.
- Assert:
  1. Exactly 20 tickets are booked (sum of successful tickets == 20).
  2. Remaining requests fail gracefully with HTTP 400 (`INSUFFICIENT_TICKETS`).
  3. `available_tickets` in PostgreSQL ends at exactly 0.
  4. No deadlocks or unhandled 500 exceptions occur.

## 3. Standard Test Execution Commands
- Run all tests: `pytest backend/tests -v`
- Run auth tests: `pytest backend/tests/test_auth -v`
- Run concurrency tests: `pytest backend/tests/test_bookings/test_concurrency.py -v`
