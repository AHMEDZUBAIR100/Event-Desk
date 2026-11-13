# EventDesk Task Board

## Status Categories: `TODO`, `IN_PROGRESS`, `IN_REVIEW`, `DONE`

| Task ID | Title | Assigned Agent | Status | Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| **TASK-001** | Day 0: Repository skeleton, documentation & Docker Compose | Lead / Orchestrator | `DONE` | None |
| **TASK-002** | Day 1: User & Auth schema with Alembic migration | Database Agent | `DONE` | TASK-001 |
| **TASK-003** | Day 1: Auth endpoints (register, login, refresh, logout, me) | Backend Agent | `DONE` | TASK-002 |
| **TASK-004** | Day 1: Frontend base scaffold & auth pages | Frontend Agent | `IN_REVIEW` | TASK-003 |
| **TASK-005** | Day 2: Events schema & endpoints (CRUD, listing, filter) | Database + Backend | `DONE` | TASK-003 |
| **TASK-006** | Day 2: Frontend event catalogue & detail view | Frontend Agent | `IN_REVIEW` | TASK-005 |
| **TASK-007** | Day 3: Booking & Cancellation service with row locking | Backend + Database | `TODO` | TASK-005 |
| **TASK-008** | Day 3: Concurrency proof test (50 concurrent requests) | Backend Agent | `TODO` | TASK-007 |
| **TASK-009** | Day 4: Reviews, WebSockets & Celery background tasks | Backend + Frontend | `TODO` | TASK-007 |
| **TASK-010** | Day 5: Dashboards, CI integration & full test audit | All | `TODO` | TASK-009 |

## Verification evidence (2026-11-13)

- Backend: `cd backend && .venv/bin/python -m pytest -q` → **121 passed**.
- Frontend: `cd frontend && npm run lint && npm run typecheck && npm run build` → **passed**.
- Frontend smoke test: `/events`, `/login`, `/register`, and `/events/{id}` returned `200`; `/bookings` redirected to `/login`; `/api/v1/events` proxied to FastAPI with `200`.
- Frontend foundation follows `docs/PROPOSAL.md` (neutral palette, Inter, light/dark mode, responsive catalogue/detail/auth views).

