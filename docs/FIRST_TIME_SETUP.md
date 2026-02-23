# First-Time Setup Guide

This guide walks you through initializing a fresh Simple Secrets Manager deployment using only the API. You’ll skip the front-end completely. We usually recommend the first-time user wizard in the UI, so stick to these instructions only if you're deploying in a restrictive environment where browser access isn't an option.

## Prerequisites

- Backend reachable at `http://localhost:5000/api` or via proxy at `http://localhost:8080/api`
- MongoDB configured and reachable by the backend

## Step 1: Check onboarding state

```bash
curl -sS http://localhost:5000/api/onboarding/status
```

Expected on a fresh install:

```json
{"isInitialized": false, "state": "not_initialized"}
```

## Step 2: Bootstrap first admin user

```bash
curl -sS -X POST "http://localhost:5000/api/onboarding/bootstrap" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Str0ng!Passw0rd","issueToken":true}'
```

This creates the first admin account and marks onboarding complete.

## Step 3: Sign in from UI (or use the API)

- Open `http://localhost:8080`
- Use the created username/password
- Create projects/configs/secrets in the admin console

## Step 4: Acquire token for API/CLI use

### Option A: Login from CLI with username/password

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm configure --base-url http://localhost:8080/api --profile dev
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm login --profile dev
```

### Option B: Set existing token

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm auth set-token --profile dev --token "<token>"
```

## Step 5: Verify access

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm whoami --profile dev
```

## Common issues

- `System already initialized`: bootstrap was already completed.
- `Missing API token`: login or set token before calling protected endpoints.
- `Missing scope: <action>`: token does not include required action scope.
- CLI `env` export fails for multiline values: use JSON format instead.

## Security notes

- Tokens should be scoped for least privilege.
- Prefer service tokens for CI/CD and machine workloads.
- Rotate/revoke tokens regularly via `/api/auth/tokens/v2/revoke`.
