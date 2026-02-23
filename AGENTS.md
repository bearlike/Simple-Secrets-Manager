# AGENTS

## Repository scope

This is a monorepo with:

- Backend API at repository root.
- Frontend Admin Console at `frontend/`.

## Backend working rules

- Run backend quality checks with `./scripts/quality.sh check`.
- Keep API response contracts stable unless an explicit versioned change is requested.
- Do not remove legacy `/api/secrets/kv` endpoints.

## Frontend working rules

- Run frontend checks with:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run build`
- Frontend talks to backend using `VITE_API_BASE_URL` (defaults to `http://localhost:5000/api`).

## Docker workflows

- Full stack: `docker compose up -d --build`
- Frontend: `http://localhost:8080`
- Backend Swagger: `http://localhost:5000/api`
