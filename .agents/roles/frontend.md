# Frontend Agent Scope & Instructions

## Responsibilities
- Implement Next.js (App Router) pages, components, client-side state, and form interactions.
- Strictly consume generated API types (`frontend/types/`) generated from FastAPI's OpenAPI specification.
- Follow Tailwind CSS & shadcn/ui patterns for responsive, accessible UI.
- Implement TanStack Query for data fetching, caching, and optimistic UI updates.
- Handle authentication state (access token in memory/cookies, refresh rotation triggers).

## Permitted Paths
- `frontend/**`

## Forbidden Paths
- `backend/**`
- `docker-compose.yml`

## Verification Commands
- Typecheck: `npm run type-check` or `tsc --noEmit`
- Linting: `npm run lint`
- Build check: `npm run build`
