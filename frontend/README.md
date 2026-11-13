# EventDesk Frontend

Next.js App Router frontend for EventDesk. The interface follows the neutral
design system in [`../docs/PROPOSAL.md`](../docs/PROPOSAL.md): monochrome
surfaces, Inter typography, light/dark themes, and content-led event cards.

## Requirements

- Node.js 20+
- The FastAPI backend running on `http://localhost:8000`

## Setup

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. Next.js rewrites `/api/*` to the backend, so the
browser stays on one origin during local development.

## Scripts

| Command | Description |
| :--- | :--- |
| `npm run dev` | Start the development server |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript check |
| `npm run generate:api` | Regenerate `types/api.ts` from the backend OpenAPI schema |
| `npm run verify:auth` | Verify the full BFF auth lifecycle against running servers |

`generate:api` reads `../backend/openapi.json` when present, otherwise it
requests `http://localhost:8000/api/v1/openapi.json`. Override the source with
`OPENAPI_SCHEMA=/path/or/url`.

## Current scope

Implemented: design tokens, light/dark themes, responsive shell and mobile
navigation, authentication pages, the public event catalogue with filters and
pagination, and the event detail view.

Not implemented yet: ticket booking, reviews, notifications, dashboards, and
admin screens. Those depend on backend endpoints that are still on the build
plan. The booking button on the event detail page is intentionally disabled
rather than calling an undocumented endpoint.

## Authentication flow

The browser never receives the refresh token. Same-origin server routes in
`app/api/auth/` act as a thin BFF over the FastAPI auth contract:

| Route | Behaviour |
| :--- | :--- |
| `POST /api/auth/login` | Calls FastAPI login, sets the refresh token in an HttpOnly cookie, and returns only the access token and user profile. |
| `POST /api/auth/refresh` | Reads the HttpOnly cookie, rotates the refresh token through FastAPI, updates the cookie, and returns a new access token. |
| `POST /api/auth/session` | Restores a page reload by rotating the cookie and issuing a new access token. |
| `POST /api/auth/logout` | Tries logout with the current access token. If it is expired/missing, it rotates the refresh token first and then revokes the rotated token with the fresh access token. The cookie is cleared only after a confirmed 204/2xx or an expected already-invalid 401. Unexpected backend/network failures return an error and preserve the session so logout can be retried. |

Security properties:

- Refresh cookie: `HttpOnly`, `SameSite=Lax`, `Path=/`; `Secure` is enabled in
  production (and requires HTTPS there). Local development uses HTTP.
- Access token: held in JavaScript memory only. It is not written to
  `localStorage`, `sessionStorage`, or a readable cookie.
- Middleware gates `/bookings`, `/dashboard`, and `/admin` by the presence of the
  HttpOnly refresh cookie; the API remains the actual authorization boundary.
- Refresh-token rotation and revocation are enforced by the backend database.
- A failed logout keeps the local user signed in and the HttpOnly cookie intact;
  the UI reports the error so the action can be retried. If rotation succeeded
  before revocation failed, the rotated token replaces the cookie so the retry
  can revoke it.

`npm run verify:auth` exercises login, session restore, rotation, refresh-token
reuse rejection, logout with a valid access token, logout with an expired access
token, and post-logout refresh rejection. It requires the backend and frontend
to be running and uses the local Docker Postgres to clean up its test account.
Run it against `npm run build && npm start` so the cookie is also checked for
`Secure`; when verifying a plain-HTTP `npm run dev` server, set
`EXPECT_SECURE_COOKIE=false`.
