# EventDesk 🎟️

> Production-grade, concurrency-safe Event Management & Ticket Booking Web Application.

Built with **FastAPI**, **SQLAlchemy 2.0 (Async)**, **PostgreSQL 16**, **Redis**, **Celery**, and **Next.js (App Router)**.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (asyncpg), Alembic, Pytest, WebSockets.
- **Frontend**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zod.
- **Data & Message Infrastructure**: PostgreSQL 16, Redis 7 (pub/sub & Celery broker), Mailpit (local transactional email).
- **Architecture**: Row-level locking (`SELECT ... FOR UPDATE`) to guarantee zero overselling under concurrent booking requests.

---

## 📁 Repository Structure

```text
eventdesk/
├── AGENTS.md                  # Master rules and conventions for coding agents
├── docker-compose.yml         # Local Postgres, Redis, and Mailpit containers
├── .env.example               # Template environment configuration
├── docs/                      # Canonical specs (Architecture, ERD, API Contract, ADRs)
├── .agents/roles/             # Specialist role guides (backend, frontend, db, reviewer)
├── backend/                   # FastAPI backend, migrations, and test suite
└── frontend/                  # Next.js App Router application
```

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Node.js 20+

### 2. Start Services
```bash
cp .env.example .env
docker compose up -d
```
Verify running services:
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Mailpit Web UI: `http://localhost:8025`

### 3. Documentation
Before developing features, review the core specifications:
- [System Architecture](docs/ARCHITECTURE.md)
- [Entity-Relationship Diagram (ERD)](docs/ERD.md)
- [API Contract](docs/API_CONTRACT.md)
- [Architecture Decisions (ADRs)](docs/DECISIONS.md)
