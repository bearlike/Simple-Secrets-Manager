# First-Time Setup Guide

This guide initializes a fresh Simple Secrets Manager deployment.

## Prerequisites

- Backend reachable at `http://localhost:5000/api` or `http://localhost:8080/api`
- MongoDB configured and reachable by backend
- `uv` installed if you want CLI access

## Step 1: Check onboarding state

```bash
curl -sS http://localhost:5000/api/onboarding/status
```

Expected on fresh install:

```json
{"isInitialized": false, "state": "not_initialized"}
```

## Step 2: Bootstrap first admin user

```bash
curl -sS -X POST "http://localhost:5000/api/onboarding/bootstrap" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Str0ng!Passw0rd","issueToken":true}'
```

## Step 3: Sign in from UI

- Open `http://localhost:8080`
- Sign in with created username/password
- Create projects/configs/secrets

## Step 4: Install CLI (once)

```bash
uv tool install git+https://github.com/bearlike/Simple-Secrets-Manager.git
uv tool update-shell
ssm-cli --help
```

If already installed, update:

```bash
uv tool upgrade simple-secrets-manager
```

If needed:

```bash
export PATH="$(uv tool dir --bin):$PATH"
```

## Step 5: Authenticate CLI

Option A: Login with username/password

```bash
ssm-cli configure --base-url http://localhost:8080/api --profile dev
ssm-cli login --profile dev
```

Option B: Use an existing token

```bash
ssm-cli auth set-token --profile dev --token "<token>"
```

## Step 6: Verify access

```bash
ssm-cli whoami --profile dev
```

Optionally verify workspace endpoints with the same token:

```bash
curl -sS http://localhost:5000/api/me \
  -H "Authorization: Bearer <token>"
curl -sS http://localhost:5000/api/workspace/members \
  -H "Authorization: Bearer <token>"
```

## Workspace RBAC quick notes (v1.4.0)

- Default bootstrap user is created as workspace `owner`.
- Workspace roles: `owner`, `admin`, `collaborator`, `viewer`.
- Project roles: `admin`, `collaborator`, `viewer`, `none`.
- Username/password is for token issuance only; app APIs are token-authorized.
- Group-based project permissions are managed via:
  - `/api/workspace/groups`
  - `/api/workspace/groups/<slug>/members`
  - `/api/workspace/projects/<project>/members`
  - `/api/workspace/group-mappings`

## Common issues

- `System already initialized`: bootstrap already completed.
- `Missing API token`: login or set token first.
- `Missing scope: <action>`: token lacks required scope.
- `.env` export fails for multiline values: use JSON format.

## Security notes

- Scope tokens with least privilege.
- Prefer service tokens for CI/CD.
- Rotate/revoke tokens via `/api/auth/tokens/v2/revoke`.
