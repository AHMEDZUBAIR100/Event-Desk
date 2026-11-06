# Database Agent Scope & Instructions

## Responsibilities
- Owns SQLAlchemy declarative models, relationships, table constraints, indices, and Alembic migrations.
- Maintains and updates `docs/ERD.md` with accurate Mermaid diagrams and column definitions.
- Designs safe migrations (nullable additions, backward-compatible changes, appropriate indices).
- Configures soft-delete filter helpers and index definitions for active records.

## Permitted Paths
- `backend/app/models/**`
- `backend/app/db/**`
- `backend/migrations/**`
- `backend/alembic.ini`
- `docs/ERD.md`

## Forbidden Paths
- `frontend/**`
- `backend/app/routers/**`

## Verification Commands
- Check migration generation: `alembic check` or `alembic upgrade head`
- Test migrations downgrade & upgrade cycle: `alembic downgrade -1 && alembic upgrade head`
