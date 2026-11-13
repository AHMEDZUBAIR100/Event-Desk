# EventDesk laptop setup

This repository uses separate dependency managers for Python, Node.js, and Docker. Their source-of-truth files are:

- `requirements.txt` → backend Python dependencies from `backend/pyproject.toml`, including test and lint tools.
- `frontend/package.json` and `frontend/package-lock.json` → Next.js and frontend libraries.
- `docker-compose.yml` → PostgreSQL 16, Redis 7, Mailpit, and pgAdmin containers.

## Prerequisites

- Git
- Docker Desktop (Windows/macOS) or Docker Engine with Docker Compose v2 (Linux)
- Python 3.12
- Node.js 20+ with npm

Docker must be running. Internet access is needed the first time you install Python/npm packages or pull container images.

## Download the project and install dependencies

Clone the repository (or download and extract its ZIP), then run these commands from the project root.

```bash
cp -n .env.example .env
cp -n frontend/.env.example frontend/.env.local

python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -r requirements.txt

cd frontend
npm ci
cd ..

docker compose up -d
```

`npm ci` installs the exact frontend dependency versions in the lockfile. Docker Compose pulls the required service images if they are not already on the laptop.

### Windows PowerShell notes

Use `py -3 -m venv backend/.venv` to create the virtual environment (confirm it selects Python 3.12 or newer). Install Python dependencies with:

```powershell
backend/.venv/Scripts/python.exe -m pip install --upgrade pip
backend/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

PowerShell copies the environment templates only when the local files do not already exist:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path frontend/.env.local)) { Copy-Item frontend/.env.example frontend/.env.local }
```

## Initialize the database

Run migrations once after the containers are healthy:

```bash
cd backend
.venv/bin/alembic upgrade head
cd ..
```

On Windows, use `.venv\Scripts\alembic.exe upgrade head` while inside `backend`.

## Run EventDesk

Open two terminals in the project root.

**Terminal 1 — API:**

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

On Windows PowerShell, run `.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000` from `backend`.

**Terminal 2 — frontend:**

```bash
cd frontend
npm run dev
```

Open <http://localhost:3000>. The public event catalogue is at <http://localhost:3000/events>, and the FastAPI docs are at <http://localhost:8000/docs>.

## Optional checks

```bash
cd frontend
npm run lint
npm run typecheck
npm run build

cd ../backend
.venv/bin/python -m pytest -q
```

The auth lifecycle verifier additionally requires the API, frontend, and local Postgres to be running. See `frontend/README.md` for `npm run verify:auth` details.
