# Implementation Proposal: Day 1 (Remaining) – Authentication Endpoints

**Review Status**: `PENDING`
**Scope**: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`
**Prerequisite**: Day 2 Users API / RBAC work is implemented and green (`34 passed`, Ruff clean, `alembic check` clean).

---

## 1. Overview & Objectives

Complete the authentication surface defined in `docs/API_CONTRACT.md` §1 using the already
available primitives:

- `app/core/security.py` — `hash_password`, `verify_password`, `create_access_token`, `hash_token`
- `app/auth/token_service.py` — `create_refresh_token`, `get_valid_refresh_token`, `revoke_user_tokens`
- `app/auth/dependencies.py` — `get_current_user`, `require_role`, `ownership_check`
- `User` / `RefreshToken` models with the partial unique active-email index

Goals:

1. Self-service registration with safe role handling.
2. Credential login returning an access/refresh token pair plus the user profile.
3. Refresh-token rotation with replay resistance and concurrent-rotation safety.
4. Logout that revokes the presented refresh token.
5. No database schema changes; reuse the existing `users` and `refresh_tokens` tables.
6. Keep `docs/API_CONTRACT.md` in sync with exact request/response payloads.

Out of scope for this iteration: email verification, password reset, OAuth/social login,
rate limiting/account lockout, WebSocket auth, and a global `{detail, code, status_code}`
error envelope. These remain follow-ups (see §9).

---

## 2. Decisions Adopted by This Plan

These resolve the ambiguities identified during the Day 2 review. They are called out here so
the reviewer can approve or override them before implementation starts.

| # | Decision | Default adopted |
| :--- | :--- | :--- |
| D1 | Refresh/logout token transport | JSON body field `refresh_token`, not a cookie or `Authorization` header |
| D2 | Self-registration roles | `attendee` (default) and `organizer`; `admin` is rejected with `403` |
| D3 | Register response | `201 Created` returning `UserRead` only; no automatic token issuance |
| D4 | `GET /auth/me` | Deferred; `/api/v1/users/me` remains the canonical profile endpoint |
| D5 | Error shape | Existing FastAPI `{"detail": "..."}` shape for consistency with current routes; global envelope is a follow-up |
| D6 | Email handling | Normalize to lowercase on write; case-insensitive lookup on login |
| D7 | Access-token claims | `sub`, `role`, `type="access"`, `exp` (refresh tokens remain opaque random strings) |

If any decision is rejected, the affected schemas, tests, and contract rows must be updated
before coding proceeds.

---

## 3. Affected Files & Components

### New files

| Path | Purpose |
| :--- | :--- |
| `backend/app/schemas/auth.py` | Request/response Pydantic v2 schemas for auth. |
| `backend/app/auth/service.py` | Registration, authentication, token issuance/rotation, logout logic. |
| `backend/app/auth/router.py` | Thin `/auth/*` endpoints and HTTP status mapping. |
| `backend/tests/test_auth/test_endpoints.py` | End-to-end endpoint tests (register → login → refresh → logout). |
| `backend/tests/test_auth/test_auth_service.py` | Service-level tests for rotation, revocation, duplicate email, inactive users. |

### Modified files

| Path | Change |
| :--- | :--- |
| `backend/app/auth/token_service.py` | Add locked refresh lookup, single-token revocation, and rotation helper. |
| `backend/app/schemas/__init__.py` | Export the new auth schemas. |
| `backend/app/main.py` | `app.include_router(auth_router, prefix=settings.API_V1_STR)`. |
| `docs/API_CONTRACT.md` | Document exact request/response bodies, status codes, and role rules. |

### Not touched

- `backend/app/models/**`, `backend/alembic/**` — no schema changes.
- `backend/app/users/**` — existing user/RBAC endpoints stay unchanged.
- `frontend/**` — no frontend exists yet.

---

## 4. API Design

All endpoints live under `/api/v1/auth` and accept/return JSON.

### 4.1 `POST /auth/register` — public

Request:

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "full_name": "Jane Doe",
  "role": "attendee"
}
```

Rules:

- `email`: `EmailStr`, normalized to lowercase before insert and lookup.
- `password`: 8–128 characters.
- `full_name`: 1–255 characters.
- `role`: `attendee` or `organizer`; `admin` → `403`.
- Duplicate active email → `409 Conflict`.
- A soft-deleted account's email may be reused (existing partial unique index).

Responses:

| Status | Body |
| :--- | :--- |
| `201` | `UserRead` (no tokens) |
| `403` | `{"detail": "Admin accounts cannot be self-registered."}` |
| `409` | `{"detail": "An account with this email already exists."}` |
| `422` | Pydantic validation errors |

### 4.2 `POST /auth/login` — public

Request:

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!"
}
```

Behavior:

- Case-insensitive email lookup, excluding `deleted_at IS NOT NULL`.
- Verify Argon2 hash.
- Reject `is_active = false` and soft-deleted users.
- Return one generic `401` for every failure reason (no user enumeration).

Response `200`:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<opaque-random-token>",
  "token_type": "bearer",
  "expires_in": 900,
  "user": { "...UserRead..." }
}
```

### 4.3 `POST /auth/refresh` — public (valid refresh token required)

Request:

```json
{ "refresh_token": "<opaque-random-token>" }
```

Behavior (single transaction):

1. Hash the incoming token and select its row with `SELECT ... FOR UPDATE`.
2. Reject if missing, already revoked, or expired.
3. Load the owning user; reject if soft-deleted or inactive.
4. Mark the old token `revoked = true`.
5. Create a new refresh token for the same user.
6. Commit, then mint a new access token (no external side effects before commit).

Response `200`: same shape as login (`access_token`, `refresh_token`, `token_type`,
`expires_in`, `user`). Any invalid/expired/revoked/reused token → `401`.

### 4.4 `POST /auth/logout` — authenticated

Headers: `Authorization: Bearer <access_token>`

Request:

```json
{ "refresh_token": "<opaque-random-token>" }
```

Behavior:

- Look up the refresh token by hash.
- Only revoke it if it belongs to the authenticated user.
- Always return `204 No Content`, even if the token is missing, already revoked, or owned by
  another user (prevents enumeration and makes logout idempotent).

### 4.5 Deferred

`GET /auth/me` is listed in the contract but is not part of this iteration (D4). The contract
row will note that `/users/me` is the canonical alternative, and the alias can be added later
without schema changes.

---

## 5. Schema Definitions (`backend/app/schemas/auth.py`)

```text
RegisterRequest
  email: EmailStr
  password: str (min_length=8, max_length=128)
  full_name: str (min_length=1, max_length=255)
  role: UserRole = UserRole.ATTENDEE

LoginRequest
  email: EmailStr
  password: str (min_length=1)

RefreshRequest
  refresh_token: str (min_length=1)

LogoutRequest
  refresh_token: str (min_length=1)

TokenPair
  access_token: str
  refresh_token: str
  token_type: str = "bearer"
  expires_in: int   # seconds, ACCESS_TOKEN_EXPIRE_MINUTES * 60

AuthResponse(TokenPair)
  user: UserRead    # imported from app.schemas.users
```

`UserRead` remains the single public user representation. No password/hash/token fields are
ever serialized.

---

## 6. Service & Token-Service Changes

### 6.1 `backend/app/auth/token_service.py` additions

| Function | Behavior |
| :--- | :--- |
| `get_refresh_token(db, raw_token, *, include_revoked=False, for_update=False)` | Hash + select one token; optional `with_for_update()` for rotation. |
| `revoke_refresh_token(db, raw_token) -> bool` | Set `revoked=True` on one matching token; returns whether a row changed. |
| `rotate_refresh_token(db, raw_token) -> tuple[str, RefreshToken, User]` | Locked lookup → validate → revoke old → create new (flush only; caller commits). |

Existing `create_refresh_token`, `get_valid_refresh_token`, and `revoke_user_tokens` remain
unchanged. New helpers raise typed domain errors or return `None`; HTTP mapping stays in the
service/router.

### 6.2 `backend/app/auth/service.py`

```text
register_user(db, payload) -> User
  - reject role == ADMIN
  - normalize email
  - pre-check active email; catch IntegrityError for the race and map to 409
  - hash_password, insert, commit, refresh

authenticate_user(db, email, password) -> User
  - case-insensitive active lookup
  - verify_password; generic 401 on mismatch/missing/inactive/deleted
  - optional dummy-hash verification on missing user to reduce timing leakage

issue_token_pair(db, user) -> TokenPair
  - create_refresh_token(...)
  - create_access_token(user.id, extra_claims={"role": user.role.value, "type": "access"})
  - expires_in from settings

login(db, payload) -> AuthResponse
  - authenticate_user + issue_token_pair + commit

rotate_tokens(db, raw_token) -> AuthResponse
  - token_service.rotate_refresh_token + issue new access token + commit

logout(db, user, raw_token) -> None
  - revoke only if owned by `user`; commit
```

Transaction rule: refresh-token rotation and revocation happen inside one database
transaction. No Celery/Redis/WebSocket/email side effects exist in these flows.

### 6.3 Router (`backend/app/auth/router.py`)

```text
router = APIRouter(prefix="/auth", tags=["Authentication"])

POST /register  -> 201 UserRead
POST /login     -> 200 AuthResponse
POST /refresh   -> 200 AuthResponse
POST /logout    -> 204, Depends(get_current_user)
```

The router only validates HTTP input and translates service exceptions into status codes. All
business logic stays in `service.py`.

### 6.4 `backend/app/main.py`

```python
from app.auth.router import router as auth_router
...
app.include_router(auth_router, prefix=settings.API_V1_STR)
```

No duplicate/unprefixed mounting (same rule applied to the users router).

---

## 7. Tests

### 7.1 Registration (`test_endpoints.py`)

- 201 for attendee and organizer; password is hashed (never equal to input).
- `role=admin` → 403 and no row inserted.
- Duplicate active email → 409; soft-deleted email can be reused.
- Weak/short password, invalid email, blank full name → 422.
- Response never contains `hashed_password`.

### 7.2 Login

- Correct credentials → 200 with both tokens, `token_type`, `expires_in`, and user profile.
- Wrong password, unknown email, inactive user, soft-deleted user → generic 401.
- Returned access token authorizes `GET /api/v1/users/me`.
- Email lookup is case-insensitive.

### 7.3 Refresh

- Valid token → 200 and a **different** refresh token.
- Old token is rejected on a second use → 401.
- Expired token → 401; malformed token → 401.
- User deactivated/soft-deleted after issuance → 401.
- Concurrent refresh with the same token: exactly one succeeds (row lock); the other is 401.
- Raw tokens are never stored; only SHA-256 hashes exist in `refresh_tokens`.

### 7.4 Logout

- `204` and the token is revoked.
- Repeating logout is still `204` (idempotent).
- A token belonging to another user is not revoked.
- Missing/invalid access token → 401.
- After logout, refreshing with the revoked token → 401.

### 7.5 Full flow

- register → login → authenticated request → refresh → logout → refresh fails.
- Existing `tests/test_users`, `tests/test_auth`, and `tests/test_schema` stay green.

### 7.6 Fixtures

Reuse `db_session`, `client`, `admin_user`, `organizer_user`, `attendee_user`, and
`deactivated_user` from `backend/tests/conftest.py`. Auth tests may build small local helpers
for login/refresh payloads but must not reach into another test's rows.

---

## 8. Verification Commands

```bash
cd backend
./.venv/bin/ruff check app tests
./.venv/bin/ruff format --check app tests
./.venv/bin/python -m pytest tests/test_auth -q
./.venv/bin/python -m pytest -q
./.venv/bin/alembic check
```

Manual smoke checks (after implementation):

```bash
# register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke@example.com","password":"StrongPass123!","full_name":"Smoke User","role":"attendee"}'

# login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke@example.com","password":"StrongPass123!"}'

# refresh / logout / me
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' -d '{"refresh_token":"<token>"}'
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer <access>" -H 'Content-Type: application/json' \
  -d '{"refresh_token":"<token>"}'
curl http://localhost:8000/api/v1/users/me -H "Authorization: Bearer <access>"
```

Acceptance criteria:

- All commands above pass; full suite remains green.
- No raw refresh token is persisted.
- A revoked/expired/inactive/deleted case always yields 401.
- OpenAPI shows only `/api/v1/auth/*` (no unprefixed aliases).

---

## 9. Known Limitations / Follow-ups

1. **Error envelope**: the contract's `{detail, code, status_code}` shape is not implemented
   globally; auth uses the existing `{"detail"}` shape. A dedicated follow-up should add a
   shared exception handler and update all endpoints together.
2. **`GET /auth/me`**: deferred; `/users/me` remains canonical (D4).
3. **Rate limiting / lockout**: no brute-force protection yet.
4. **Refresh-token reuse detection**: revoked tokens return 401 but do not revoke the user's
   other sessions. A token-family model can be added later.
5. **Email verification**: accounts are usable immediately after registration.
6. **Frontend integration**: `frontend/` is still a scaffold; generated types cannot be
   consumed until the Next.js app exists.
7. **Password change sessions**: `PATCH /users/me` does not revoke existing refresh tokens;
   unchanged by this plan.

---

## 10. Estimated Time

| Work | Estimate |
| :--- | :--- |
| Schemas + token-service helpers | 45 min |
| Service layer | 75 min |
| Router + `main.py` wiring | 30 min |
| API contract update | 20 min |
| Tests (endpoint + service) | 90 min |
| Full verification / fixes | 30 min |
| **Total** | **~4.5 hours** |

Adjust if any of the §2 decisions are overridden.
