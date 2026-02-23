# Developer Guide

This document contains developer-facing setup and maintenance workflows.

## Scope

- Backend API lives at repository root.
- Frontend admin console lives in `frontend/`.
- CLI package lives in `ssm_cli/`.

## Prerequisites

- Docker + Docker Compose
- Python + `uv`
- Node.js + npm

## Clone and bootstrap

```bash
git clone --depth 1 https://github.com/bearlike/simple-secrets-manager
cd simple-secrets-manager
uv sync
```

## Local backend setup

Create `.env` at repository root:

```bash
CONNECTION_STRING=mongodb://username:password@mongo.hostname:27017
TOKEN_SALT=change-me
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080
BIND_HOST=0.0.0.0
PORT=5000
```

Start backend:

```bash
uv run python3 server.py
```

## Local frontend setup

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=/api" > .env.local
npm run dev
```

## Local CLI setup

Run CLI from source during development:

```bash
uv run ssm --help
```

## Full stack via Docker Compose

```bash
docker compose up -d --build
```

Endpoints:

- Frontend: `http://localhost:8080`
- Backend API proxy: `http://localhost:8080/api`
- Backend API direct: `http://localhost:5000/api`

## Quality gates

Backend:

```bash
./scripts/quality.sh check
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Smoke checks

CLI smoke check against Docker stack:

```bash
uv run ssm configure --base-url http://localhost:8080/api --profile dev
uv run ssm whoami --profile dev
```

## Additional references

- Development details: [`docs/DEVELOPMENT.md`](DEVELOPMENT.md)
- CLI reference (user-facing): [`docs/CLI.md`](CLI.md)
- Frontend-specific notes: [`frontend/README.md`](../frontend/README.md)
