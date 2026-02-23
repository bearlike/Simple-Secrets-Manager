<h1 align="center"><a href="#"><img alt="Simple Secrets Manager" src="docs/img/gh_banner.png" /></a></h1>
<p align="center">
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Tag" src="https://img.shields.io/badge/Docker-ghcr.io%2Fbearlike%2Fsimple%E2%80%94secrets%E2%80%94manager%3Alatest-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Architecture" src="https://img.shields.io/badge/architecture-arm64v8%20%7C%20x86__64-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml"><img alt="GitHub Repository" src="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml/badge.svg"></a>
    <a href="/LICENSE"><img alt="License" src="https://img.shields.io/github/license/bearlike/simple-secrets-manager"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/wiki/First%E2%80%90Time-Usage"><img alt="Documentation" src="https://img.shields.io/badge/Wiki-docs-informational?logo=github"></a>
</p>

Secure storage, and delivery for tokens, passwords, API keys, and other secrets using HTTP API, Swagger UI or Python Package.
> `TL;DR`: Poor Man's Hashi Corp Vault

## Monorepo layout

This repository now contains:

- Backend API (Flask + MongoDB) at repository root.
- Frontend Admin Console (Vite + React) at `frontend/`.

## Why does this exist?

Hashi Corp Vault works well but it was meant for enterprises. Therefore, it was heavy and non-portable (atleast difficult) for my homelab setup. So I wanted to build a Secrets Manager intended for small scale setups that could also scale well.

## Goals

- A lightweight system that sucks less power out of the wall. Therefore, minimal background jobs and reduced resource utilizations.
- Should be compatible on both `x86-64` and `arm64v8` (mainly Raspberry Pi 4).
- High stability, availability and easy scalability.

## Available secret engines

| Secret Engine | Description                                           |
|---------------|-------------------------------------------------------|
| `kv`          | Key-Value engine is used to store arbitrary secrets.  |

## Available authentication methods

| Auth Methods      | Description                                                               |
|-------------------|---------------------------------------------------------------------------|
| `userpass`        | Allows users to authenticate using a username and password combination.   |
| `token`           | Allows users to authenticate using a token. Token generation requires users to be authenticated via `userpass`                               |

## Future

- Secret engines for certificates (PKI), SSH and databases.
- Encrypting secrets before writing to a persistent storage, so gaining access to the raw storage isn't enough to access your secrets.

## Getting started

### Automated Install: [`docker-compose`](https://docs.docker.com/compose/install/) (Recommended)

1. Run the full stack:

   ```bash
   docker compose up -d --build
   ```

2. Open:
   - Frontend: `http://localhost:8080`
   - Backend API (via reverse proxy): `http://localhost:8080/api`
   - Backend API (direct): `http://localhost:5000/api`

### Manual Installation

#### Backend setup

1. **Clone repository**

   ```bash
   git clone --depth 1 https://github.com/bearlike/simple-secrets-manager
   cd simple-secrets-manager
   ```

2. Create a `.env` file in the project root.

   ```sh
   CONNECTION_STRING=mongodb://username:password@mongo.hostname:27017
   TOKEN_SALT=change-me
   CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080
   BIND_HOST=0.0.0.0
   PORT=5000
   ```

3. **Install dependencies**

   ```bash
   uv sync
   ```

4. **Start the server**

   ```bash
   uv run python3 server.py
   ```

5. **Access the application**:
   - Frontend UI: `http://server_hostname:8080`
   - Backend Swagger UI: `http://server_hostname:5000/api` (or `http://server_hostname:8080/api`)

#### Frontend setup

1. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

2. Optionally override API base URL:

   ```bash
   echo "VITE_API_BASE_URL=/api" > .env.local
   ```

3. Start frontend dev server:

   ```bash
   npm run dev
   ```

4. Open `http://localhost:5173`.

### First-time setup (deterministic DB-stamped onboarding)

- Open frontend login (`http://localhost:5173` for dev or `http://localhost:8080` for Docker).
- If the system is not initialized, the login screen automatically switches to an **Initial Setup** wizard.
- Submit admin username/password once. Backend stamps onboarding state in MongoDB and returns a bootstrap API token.
- Frontend logs in automatically with that token.
- On subsequent launches, only token login is shown.

### Development quality checks

```bash
./scripts/quality.sh check
# or auto-fix lint/style first, then type-check and test
./scripts/quality.sh fix
```

### Git hooks (auto lint/test before push)

```bash
./scripts/install-git-hooks.sh
```

After installation:
- `pre-commit` auto-fixes Ruff issues on staged Python files.
- `pre-push` runs full lint/type/test gates and blocks push if fixes are required.

For user creation and initial setup, see the [First-Time Usage Guide](https://github.com/bearlike/simple-secrets-manager/wiki/First%E2%80%90Time-Usage).

## Environment variables

- `CONNECTION_STRING`: MongoDB connection string.
- `TOKEN_SALT`: Salt used before hashing API tokens.
- `CORS_ORIGINS`: Comma-separated list of allowed origins for `/api/*` when calling backend directly on port `5000`.
- `BIND_HOST`: Host interface used by Flask (default `0.0.0.0`).
- `PORT`: HTTP port used by Flask (default `5000`).
- `VITE_API_BASE_URL`: Frontend API base URL override (`frontend/.env.local`), defaults to `/api`.

## Developer docs

- Backend quality gates: `./scripts/quality.sh check`
- Frontend quality gates: `cd frontend && npm run lint && npm run build`
- Full guide: `docs/DEVELOPMENT.md`
- Container publish flow: `.github/workflows/ci.yml`

## CI/CD container publish

`GitHub Actions` publishes the unified image `ghcr.io/bearlike/simple-secrets-manager` automatically:

- On pushes to `main` and `feat/v1.2.0` when backend/frontend/container files change.
- On semantic version tags (`vX.Y.Z`) with semantic container tags (`X.Y.Z`, `X.Y`, `X`).
- On manual workflow dispatch (optional custom extra tag).

## API examples

Set these first:

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

Export secrets as JSON (with inherited values and metadata):

```bash
curl -sS "$BASE_URL/projects/my-project/configs/dev/secrets?format=json&include_parent=true&include_meta=true" \
  -H "Authorization: Bearer $TOKEN"
```

List scoped tokens metadata:

```bash
curl -sS "$BASE_URL/auth/tokens/v2" \
  -H "Authorization: Bearer $TOKEN"
```

Revoke token by `token_id` (preferred):

```bash
curl -sS -X POST "$BASE_URL/auth/tokens/v2/revoke" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token_id":"<token-id>"}'
```

Revoke token by plaintext token (compatibility):

```bash
curl -sS -X POST "$BASE_URL/auth/tokens/v2/revoke" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"<plaintext-token>"}'
```

Read audit events filtered by project/config slugs:

```bash
curl -sS "$BASE_URL/audit/events?project=my-project&config=dev&since=2026-01-01T00:00:00Z&limit=50" \
  -H "Authorization: Bearer $TOKEN"
```

Check onboarding status (no auth):

```bash
curl -sS "$BASE_URL/onboarding/status"
```

Bootstrap first admin and token (no auth, first-time only):

```bash
curl -sS -X POST "$BASE_URL/onboarding/bootstrap" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Str0ng!Passw0rd"}'
```
