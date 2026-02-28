# Development Details

This document is a deeper engineering reference.

For day-to-day developer onboarding, use [`docs/DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) first.

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

4. First-time bootstrap (deterministic DB-stamped onboarding):

```bash
curl -sS -X POST "http://localhost:5000/api/onboarding/bootstrap" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Str0ng!Passw0rd"}'
```

After completion, onboarding is marked complete in MongoDB and first-time bootstrap is blocked.

## Local frontend only

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=/api" > .env.local
npm run dev
```

Open `http://localhost:5173`.

## Full stack with Docker Compose

```bash
./scripts/deploy_stack.sh
```

- Frontend: `http://localhost:8080`
- Backend API via reverse proxy: `http://localhost:8080/api`
- Backend API direct: `http://localhost:5000/api`
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

CLI:

```bash
uv sync
uv run ssm-cli --help
```

Detailed CLI usage is documented in [`docs/CLI.md`](CLI.md).

## Version source of truth

- `VERSION` is the single editable application version source.
- `scripts/version_sync.py --check` validates wiring and is used in CI before Docker builds/publish.
- `scripts/deploy_stack.sh` is the local source-build deploy path and exports `APP_VERSION` from `VERSION` before running compose.
- Docker images receive `APP_VERSION` build arg from CI, and `org.opencontainers.image.version` is labeled from that arg.
- Release tags must match `VERSION` (for example `v1.4.0` for `VERSION=1.4.0`).

## Workspace RBAC model (v1.4.0)

Authorization model:

- Login uses username/password only to mint tokens (`/api/auth/tokens/...`).
- All app endpoints are bearer token authorized with computed scopes.
- Personal token scopes are computed from RBAC data each request (membership changes apply immediately).

Roles:

- Workspace: `owner`, `admin`, `collaborator`, `viewer`
- Project: `admin`, `collaborator`, `viewer`, `none`
- Effective project role is the highest of direct user assignment and group-derived assignment.

Core RBAC API routes:

- `/api/me`
- `/api/workspace/settings`
- `/api/workspace/members`
- `/api/workspace/groups`
- `/api/workspace/group-mappings`
- `/api/workspace/projects/<project_slug>/members`

## Secret reference resolution

Config export endpoint supports optional reference resolution:

- `GET /api/projects/<project>/configs/<config>/secrets?format=json|env&resolve_references=true`
- `raw=true` disables resolution and returns stored raw values.
- `placeholder_max_depth=<n>` controls recursion depth for nested references.

Supported placeholders:

- `${KEY}` (same config)
- `${config.KEY}` (another config in same project)
- `${project.config.KEY}` (config in another project)

Validation and fallback behavior:

- `PUT /api/projects/<project>/configs/<config>/secrets/<key>` validates references before save and returns `400` for invalid or unresolved references.
- If a previously valid reference becomes unavailable later (for example referenced secret deleted), read/export resolution substitutes an empty string for that placeholder.

Global CLI install smoke check:

```bash
uv tool install /absolute/path/to/Simple-Secrets-Manager
uv tool update-shell
ssm-cli --help
```

UVX distribution smoke check (ephemeral, no install):

```bash
uvx --from /absolute/path/to/Simple-Secrets-Manager ssm-cli --help
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

Application version endpoint:

```bash
curl -sS http://localhost:5000/api/version
```

The Admin Console GitHub button displays this backend-reported version so Docker-built frontend/backend stay in sync.

CLI smoke check:

```bash
uv run ssm-cli configure --base-url http://localhost:8080/api --profile dev
uv run ssm-cli whoami --profile dev
```

## CI publish flow

Container publishing is handled by `.github/workflows/ci.yml`.

- Push to `main` with container/app changes triggers build+push to GHCR.
- Other branch pushes produce branch-ref tags and short SHA tags.
- Tag push `vX.Y.Z` additionally publishes semantic tags.
- Manual dispatch can publish an extra custom tag.
