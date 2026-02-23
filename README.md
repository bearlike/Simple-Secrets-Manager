<h1 align="center"><a href="#"><img alt="Simple Secrets Manager" src="docs/img/gh_banner.png" /></a></h1>
<p align="center">
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Tag" src="https://img.shields.io/badge/Docker-ghcr.io%2Fbearlike%2Fsimple%E2%80%94secrets%E2%80%94manager%3Alatest-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Architecture" src="https://img.shields.io/badge/architecture-arm64v8%20%7C%20x86__64-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml"><img alt="GitHub Repository" src="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml/badge.svg"></a>
    <a href="/LICENSE"><img alt="License" src="https://img.shields.io/github/license/bearlike/simple-secrets-manager"></a>
    <a href="docs/DEVELOPMENT.md"><img alt="Documentation" src="https://img.shields.io/badge/Docs-Development-informational?logo=readme"></a>
</p>

Simple Secrets Manager is a lightweight, self-hosted secret manager for teams that need clean project/config-based secret organization without enterprise overhead.

<img height="720" alt="image" src="https://github.com/user-attachments/assets/539016cb-9428-4b3d-8704-31dc474caf65" />

## What it is for?

- Store secrets by `project` and `config` (`dev`, `staging`, `prod`, etc.).
- Inherit values across configs and override only where needed.
- Manage values from UI or API.
- Use username/password for humans and scoped tokens for automation.

### Quick start (Docker)

```bash
docker compose up -d --build
```

Open:

- Frontend: `http://localhost:8080`
- Backend API (proxy): `http://localhost:8080/api`
- Backend API (direct): `http://localhost:5000/api`

### First-time setup

- On a fresh install, login shows initial setup.
- Create the first admin username/password.
- Then sign in with username/password and start creating projects/configs/secrets.

For full onboarding and bootstrap flow, see [`docs/FIRST_TIME_SETUP.md`](docs/FIRST_TIME_SETUP.md).

### Standard usage flow

1. Create a project.
2. Create one or more configs.
3. Add secrets manually or import a `.env` file from the config page.
4. Export secrets in JSON or `.env` format when needed.
5. Create scoped tokens for services and CI/CD.

### CLI (Doppler-like workflow)

After `uv sync`, the CLI entrypoint is available at `.venv/bin/ssm`.

Configure base URL and set a token:

```bash
uv run ssm configure --base-url http://localhost:8080/api --profile dev
uv run ssm auth set-token --token "<service-or-personal-token>" --profile dev
```

Set directory defaults:

```bash
uv run ssm setup --project my-project --config dev --profile dev
```

Run commands with injected secrets:

```bash
uv run ssm run --profile dev -- python app.py
```

Other useful commands:

```bash
uv run ssm whoami --profile dev
uv run ssm secrets download --profile dev --format json
uv run ssm secrets mount --profile dev --path /tmp/ssm-secrets.fifo --format json
```

Command reference and detailed CLI behavior are documented in [`docs/CLI.md`](docs/CLI.md).

---

## Contributing

### Prerequisites

- Docker + Docker Compose
- Python + `uv`
- Node.js + npm

### Local backend setup

```bash
git clone --depth 1 https://github.com/bearlike/simple-secrets-manager
cd simple-secrets-manager
```

Create `.env` at repository root:

```bash
CONNECTION_STRING=mongodb://username:password@mongo.hostname:27017
TOKEN_SALT=change-me
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080
BIND_HOST=0.0.0.0
PORT=5000
```

Run backend:

```bash
uv sync
uv run python3 server.py
```

### Local frontend setup

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=/api" > .env.local
npm run dev
```

Open `http://localhost:5173`.

### Quality checks

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

### Developer docs

- Full development guide: [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
- First-time setup guide: [`docs/FIRST_TIME_SETUP.md`](docs/FIRST_TIME_SETUP.md)
- CLI reference: [`docs/CLI.md`](docs/CLI.md)
- Frontend notes: [`frontend/README.md`](frontend/README.md)

## Supplementary Reference

### Environment variables

| Variable | Description |
|----------|-------------|
| `CONNECTION_STRING` | MongoDB connection string. |
| `TOKEN_SALT` | Salt used before hashing API tokens. |
| `CORS_ORIGINS` | Comma-separated allowed origins for direct backend access on port `5000`. |
| `BIND_HOST` | Flask bind host (default `0.0.0.0`). |
| `PORT` | Flask port (default `5000`). |
| `VITE_API_BASE_URL` | Frontend API base URL override (`frontend/.env.local`), defaults to `/api`. |

### API examples

Set variables:

```bash
export BASE_URL="http://localhost:5000/api"
export TOKEN="<api-token>"
```

List projects:

```bash
curl -sS "$BASE_URL/projects" \
  -H "Authorization: Bearer $TOKEN"
```

List configs in a project:

```bash
curl -sS "$BASE_URL/projects/my-project/configs" \
  -H "Authorization: Bearer $TOKEN"
```

Export secrets (with inherited values and metadata):

```bash
curl -sS "$BASE_URL/projects/my-project/configs/dev/secrets?format=json&include_parent=true&include_meta=true" \
  -H "Authorization: Bearer $TOKEN"
```

Revoke a token by `token_id`:

```bash
curl -sS -X POST "$BASE_URL/auth/tokens/v2/revoke" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token_id":"<token-id>"}'
```

Container runtime reference: [`docs/README_dockerhub.md`](docs/README_dockerhub.md)
