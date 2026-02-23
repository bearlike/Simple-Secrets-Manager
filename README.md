<h1 align="center"><a href="#"><img alt="Simple Secrets Manager" src="docs/img/gh_banner.png" /></a></h1>
<p align="center">
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Tag" src="https://img.shields.io/badge/Docker-ghcr.io%2Fbearlike%2Fsimple%E2%80%94secrets%E2%80%94manager%3Alatest-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Architecture" src="https://img.shields.io/badge/architecture-arm64v8%20%7C%20x86__64-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml"><img alt="GitHub Repository" src="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml/badge.svg"></a>
    <a href="/LICENSE"><img alt="License" src="https://img.shields.io/github/license/bearlike/simple-secrets-manager"></a>
    <a href="docs/CLI.md"><img alt="Documentation" src="https://img.shields.io/badge/Docs-CLI-informational?logo=readme"></a>
</p>

Simple Secrets Manager is a lightweight, self-hosted secret manager for teams that need project/config-based secret organization without enterprise overhead.

<img height="720" alt="image" src="https://github.com/user-attachments/assets/539016cb-9428-4b3d-8704-31dc474caf65" />

## Product Overview

- Store secrets by `project` and `config` (`dev`, `staging`, `prod`, etc.).
- Inherit values across configs and override only where needed.
- Manage values from UI or API.
- Use username/password for humans and scoped tokens for automation.

## Quick Start (Docker)

```bash
docker compose up -d --build
```

Open:

- Frontend: `http://localhost:8080`
- Backend API (proxy): `http://localhost:8080/api`
- Backend API (direct): `http://localhost:5000/api`

## First-Time Setup

- On a fresh install, login shows initial setup.
- Create the first admin username/password.
- Then sign in and create projects/configs/secrets.

Step-by-step guide: [`docs/FIRST_TIME_SETUP.md`](docs/FIRST_TIME_SETUP.md)

## Standard Usage Flow

1. Create a project.
2. Create one or more configs.
3. Add secrets manually or import a `.env` file from the config page.
4. Export secrets in JSON or `.env` format when needed.
5. Create scoped tokens for services and CI/CD.

## CLI (UVX-first)

Run the CLI from anywhere without cloning this repository:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm-cli --help
```

Configure and authenticate:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm-cli configure --base-url http://localhost:8080/api --profile dev
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm-cli auth set-token --token "<service-or-personal-token>" --profile dev
```

Run any process with injected secrets:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm-cli run --profile dev -- python app.py
```

Detailed CLI reference: [`docs/CLI.md`](docs/CLI.md)

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

## Documentation Index

- First-time setup: [`docs/FIRST_TIME_SETUP.md`](docs/FIRST_TIME_SETUP.md)
- CLI reference: [`docs/CLI.md`](docs/CLI.md)
- Container runtime reference: [`docs/README_dockerhub.md`](docs/README_dockerhub.md)
- Developer docs: [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md)
