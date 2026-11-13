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

## Auth hardening verification (2026-11-14)

- Backend: `cd backend && .venv/bin/python -m pytest -q` → **122 passed** (includes expired-access logout fallback test).
- Frontend: `cd frontend && npm run lint && npm run typecheck && npm run build` → **passed**.
- BFF lifecycle: `cd frontend && npm run verify:auth` → **7/7 checks passed**:
  - login returns access token + HttpOnly/Secure/SameSite=Lax refresh cookie with no `refresh_token` in JSON;
  - session restore rotates the cookie and invalidates the previous token;
  - refresh rotates again and the previous token is rejected;
  - a revoked refresh token cannot be reused;
  - logout with a valid access token revokes server-side;
  - logout with an expired access token rotates first, then revokes the rotated token;
  - post-logout session restore and refresh are rejected.
- Logout failure handling (manual check with backend stopped after login): `POST /api/auth/logout` returned **503** with `{"detail":"Logout could not be completed. Please try again."}`, emitted **no clearing `Set-Cookie`**, and the refresh token remained usable (`200`) once the backend restarted. Retrying the backend logout then returned `204`.
- Access tokens are memory-only in the browser; refresh tokens are server-side HttpOnly cookies.
- Error alert tokens are monochrome (`--destructive` follows foreground/background in both themes); error states no longer introduce red.

