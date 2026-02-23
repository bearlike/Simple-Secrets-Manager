# Development Guide

## Monorepo overview

- Backend API: repository root (`server.py`, `Api/`, `Engines/`, `Access/`)
- Frontend Admin Console: `frontend/`

## Local backend only

1. Create `.env` in repo root:

```bash
CONNECTION_STRING=mongodb://root:password@localhost:27017
TOKEN_SALT=change-me
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
BIND_HOST=0.0.0.0
PORT=5000
```

2. Start backend:

```bash
uv sync
uv run python3 server.py
```

3. Verify:

```bash
curl -sS http://localhost:5000/api
```

## Local frontend only

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=http://localhost:5000/api" > .env.local
npm run dev
```

Open `http://localhost:5173`.

## Full stack with Docker Compose

```bash
docker compose up -d --build
```

- Frontend: `http://localhost:8080`
- Backend Swagger UI: `http://localhost:5000/api`
- MongoDB: `localhost:27017`

Stop:

```bash
docker compose down
```

## Quality checks

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

## Integration smoke checks

Backend health endpoint (Swagger index):

```bash
curl -sS http://localhost:5000/api | head
```

Frontend HTTP check:

```bash
curl -sS -I http://localhost:8080
```
