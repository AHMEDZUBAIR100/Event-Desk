# Backend Agent Scope & Instructions

## Responsibilities
- Implement FastAPI routes, services, Pydantic schemas, and backend tests.
- Strictly adhere to `docs/API_CONTRACT.md` and `docs/ERD.md`.
- Enforce RBAC dependencies (`admin`, `organizer`, `attendee`) and ownership verification.
- Implement concurrency-safe booking logic with row locks (`SELECT ... FOR UPDATE`).
- Ensure notifications and WebSocket events are fired after commit.

## Permitted Paths
- `backend/app/` (except modifying models/migrations directly without DB agent alignment)
- `backend/tests/`
- `docs/API_CONTRACT.md` (updates must be reviewed)

## Forbidden Paths
- `frontend/**`
- `backend/migrations/**` (owned by Database Agent)

## Quality & Verification Commands
- Linting: `ruff check backend/app`
- Formatting: `ruff format backend/app`
- Tests: `pytest backend/tests -v`
