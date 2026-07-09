# Contributing

This is the contributor entry point: prerequisites, bootstrap, local runs,
quality gates, smoke checks, and commit conventions. For product-level docs
(CLI usage, deployment, the reloader), see [`docs/README.md`](README.md).

## Prerequisites

- Docker + Docker Compose
- Python 3.13+ + `uv`
- Node.js + npm

## Clone and bootstrap

```bash
git clone --depth 1 https://github.com/bearlike/simple-secrets-manager
cd simple-secrets-manager
uv sync --all-extras
```

`uv sync --all-extras` pulls in the `server` and `reload` extras on top of
the lean CLI-only base install, so the whole monorepo imports locally.

### Monorepo layout

- Backend API: `ssm_server/` (`api/`, `engines/`, `access/`, `connection.py`, `main.py`)
- CLI client: `ssm_cli/`
- Container reloader: `ssm_reload/`
- Frontend admin console: `frontend/`
- Tests: `tests/{server,cli,reload}`

Dependencies are split in `pyproject.toml`: the base install is CLI-only
(what `ssm_cli` actually imports); the `server` extra adds Flask/flask-restx/
PyMongo; the `reload` extra adds the Docker SDK; `all` pulls in both for a
full local checkout (`uv sync --all-extras`).

## Local runs

### Backend

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
uv run python -m ssm_server.main
```

Verify:

```bash
curl -sS http://localhost:5000/api
```

First-time bootstrap (deterministic DB-stamped onboarding — see
[`docs/FIRST_TIME_SETUP.md`](FIRST_TIME_SETUP.md) for the full flow):

```bash
curl -sS -X POST "http://localhost:5000/api/onboarding/bootstrap" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Str0ng!Passw0rd"}'
```

### Frontend

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=/api" > .env.local
npm run dev
```

### CLI

Run CLI from source during development:

```bash
uv run ssm-cli --help
```

Install CLI globally for manual QA outside repo:

```bash
uv tool install git+https://github.com/bearlike/Simple-Secrets-Manager.git
uv tool update-shell
ssm-cli --help
```

If needed:

```bash
export PATH="$(uv tool dir --bin):$PATH"
```

### Full stack via Docker Compose

```bash
./scripts/deploy_stack.sh
```

Endpoints:

- Frontend: `http://localhost:8080`
- Backend API proxy: `http://localhost:8080/api`
- Backend API direct: `http://localhost:5000/api`

## Quality gates & pre-commit

Backend (front door, or call the script directly):

```bash
make check
# or: ./scripts/quality.sh check
```

Install the fast pre-commit gate once per checkout:

```bash
make precommit-install
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Smoke checks

CLI smoke check against the Docker stack:

```bash
uv run ssm-cli configure --base-url http://localhost:8080/api --profile dev
uv run ssm-cli whoami --profile dev
```

Backend health endpoint (Swagger index):

```bash
curl -sS http://localhost:5000/api | head
```

Frontend HTTP check:

```bash
curl -sS -I http://localhost:8080
```

Application version endpoint (the Admin Console's GitHub button displays
this backend-reported version, so Docker-built frontend/backend stay in
sync):

```bash
curl -sS http://localhost:5000/api/version
```

Workspace RBAC smoke checks:

```bash
curl -sS http://localhost:5000/api/me -H "Authorization: Bearer <token>"
curl -sS http://localhost:5000/api/workspace/members -H "Authorization: Bearer <token>"
curl -sS http://localhost:5000/api/workspace/groups -H "Authorization: Bearer <token>"
```

Role quick reference:

- Workspace roles: `owner`, `admin`, `collaborator`, `viewer`
- Project roles: `admin`, `collaborator`, `viewer`, `none`
- Group/project assignments are managed under `/api/workspace/*`.

## Commit conventions

Gitmoji plus Conventional Commits. Format:

```
<gitmoji> <type>(<scope>): <imperative description>

<optional body>

<optional footer>
```

| Type | Emoji | When |
| --- | --- | --- |
| build | 🏗️ | build system / external deps |
| chore | 🔧 | non-src/test changes (scripts, config) |
| ci | 👷 | CI config and scripts |
| docs | 📝 | documentation only |
| feat | ✨ | a new feature |
| fix | 🐛 | a bug fix |
| perf | ⚡️ | performance improvement |
| refactor | ♻️ | neither fixes a bug nor adds a feature |
| revert | ⏪️ | reverts a previous commit |
| style | 💄 | formatting only, no behavior change |
| test | ✅ | add/fix tests |
| i18n | 🌐 | internationalization |

Scope is the core project/lib being worked on (`api`, `frontend`, `cli`,
`engines`, `access`, …). Description is imperative ("add", not "added").
Examples: `✨ feat(api): add ability to parse arrays`,
`🐛 fix(frontend): correct button alignment`.

## Additional references

- CLI reference (user-facing): [`docs/CLI.md`](CLI.md)
- Frontend-specific notes: [`frontend/README.md`](../frontend/README.md)
- Documentation index: [`docs/README.md`](README.md)
