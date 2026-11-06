# Agent Ownership & Boundaries

| Role | Primary Ownership | Permitted Paths | Strictly Forbidden |
| :--- | :--- | :--- | :--- |
| **Lead / Orchestrator** | Task board, PR reviews, integration approvals, roadmap | All (for coordination) | Silent feature rewrites |
| **Backend Agent** | FastAPI routes, services, Pydantic schemas, backend tests | `backend/app/`, `backend/tests/`, `docs/API_CONTRACT.md` | `frontend/**`, modifying DB schema independently |
| **Database Agent** | SQLAlchemy models, Alembic migrations, database constraints | `backend/app/models/`, `backend/migrations/`, `docs/ERD.md` | `frontend/**`, `backend/app/routers/**` |
| **Frontend Agent** | Next.js App Router, components, forms, client state | `frontend/**` | `backend/**`, `docker-compose.yml` |
| **Reviewer / QA** | Code quality, security checks, test coverage verification | Read-Only across entire repo | Direct implementation fixes without task assignment |
| **Integration Agent**| Main branch merging, CI checks, tag releases | Root repo, git branch merges | Bypassing review gates |
