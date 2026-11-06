# EventDesk — Master Agent Instructions & Rules

Events and concurrency-safe ticket booking platform.
- **Backend**: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16 + Redis + Celery + WebSockets.
- **Frontend**: Next.js (App Router) + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query.

---

## 1. Global Operating Rules for All Agents

1. **Read-Before-Edit**:
   - Before modifying or adding code, read this file (`AGENTS.md`), your role instructions in `.agents/roles/<role>.md`, and the canonical documents in `docs/` (`ARCHITECTURE.md`, `ERD.md`, `API_CONTRACT.md`, `DECISIONS.md`).
2. **Never Invent Contracts**:
   - The API and Database schemas are strictly defined in `docs/API_CONTRACT.md` and `docs/ERD.md`.
   - Frontend must strictly consume generated types or documented contracts. Do not invent endpoints or payload fields.
   - Backend must not change response formats without updating `docs/API_CONTRACT.md`.
   - Database agent must publish and get review on schema changes before backend implements them.
3. **No Direct Master/Main Commits**:
   - Do not run `git commit` or `git push` without explicit user permission.
   - Integration / Commit agent or user handles merges into `main`.
4. **Environment & Secrets**:
   - Never hardcode secrets, API keys, or production passwords.
   - Read configurations exclusively from environment variables via `backend/app/core/config.py`.
   - Keep `.env.example` updated with placeholder-only values.
5. **Dependencies**:
   - Do not add new external third-party dependencies without explicit user confirmation.

---

## 2. Architecture & Code Guidelines

### Backend Standards:
- **Module Structure**: `backend/app/{core,db,models,schemas,auth,users,events,bookings,reviews,notifications,audit,realtime,tasks}/`
- **Separation of Concerns**: Each domain feature module must maintain:
  - `router.py`: Thin endpoints handling HTTP validation and status codes.
  - `service.py`: Pure business logic, database queries, and transaction management.
  - `schemas.py`: Pydantic v2 schemas for requests and responses.
- **Booking & Concurrency (Critical Rule)**:
  - Booking and ticket cancellations must run inside a single PostgreSQL database transaction using row-level locking (`SELECT ... FOR UPDATE` on the event row).
  - Never trust a read-then-write approach. Prevent overselling at the database level.
- **Database & Soft Deletes**:
  - Soft delete (`deleted_at` timestamp) is used for users, events, and bookings.
  - Default database queries must always exclude soft-deleted rows.
- **Role-Based Access Control (RBAC)**:
  - Roles: `admin`, `organizer`, `attendee`.
  - Enforce permissions via reusable FastAPI dependencies (e.g., `get_current_active_user`, `require_role(...)`), never inline ad-hoc `if` checks in routers.
  - Prevent IDOR (Insecure Direct Object Reference): organizers can only edit their own events.
- **Audit Logging**:
  - Critical actions (event creation/updates, ticket bookings, cancellations, role changes) must insert a record into the `audit_log` table.
- **Async Side Effects**:
  - Background tasks, Celery jobs, email dispatches, and WebSocket broadcast pushes must trigger **AFTER** the database transaction commits successfully. Never dispatch notifications inside uncommitted transactions.
- **Testing & Code Quality**:
  - Full type hints everywhere. Ruff for formatting and linting.
  - Pytest test suite in `backend/tests/` mirroring `backend/app/`.
  - Must include the real Postgres 50-concurrent-request booking test.

### Frontend Standards:
- **Type Safety**:
  - Use API types generated via `openapi-typescript` from FastAPI's OpenAPI JSON schema.
- **State & Data Fetching**:
  - Use TanStack Query for server state caching, pagination, optimistic updates, and loading states.
- **Form Handling**:
  - Use `react-hook-form` paired with `zod` validation schemas that mirror the backend constraints.
- **UI Components**:
  - Tailwind CSS + shadcn/ui components in `components/ui/`.
  - Maintain clean accessibility and responsive layouts.

---

## 3. Directory Layout

```text
eventdesk/
├── AGENTS.md                  # Global rules (this file)
├── docker-compose.yml         # Postgres 16, Redis, Mailpit
├── .env.example               # Safe environment variable placeholders
├── .gitignore
├── docs/                      # Canonical specs (ERD, ARCHITECTURE, API_CONTRACT)
├── .agents/roles/             # Role instructions (backend, frontend, database, reviewer, integration)
├── backend/                   # FastAPI application & tests
└── frontend/                  # Next.js App Router application
```

---

## 4. Handoff Checklist Format
When completing a task, always report:
1. **Task ID & Summary**
2. **Files Created/Modified**
3. **Contract / Schema Changes** (if any, with links to updated docs)
4. **Exact Test Commands Run & Results**
5. **Known Limitations / Next Steps**
