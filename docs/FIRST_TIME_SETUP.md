# First-Time Setup Guide

This guide covers the first initialization of a fresh Simple Secrets Manager deployment.

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

## Step 3: Sign in from UI

- Open `http://localhost:8080`
- Use the created username/password
- Create projects/configs/secrets in the admin console

## Step 4: Acquire token for API/CLI use

### Option A: Login from CLI with username/password

```bash
uv run ssm configure --base-url http://localhost:8080/api --profile dev
uv run ssm login --profile dev
```

### Option B: Set existing token

```bash
uv run ssm auth set-token --profile dev --token "<token>"
```

## Step 5: Verify access

```bash
uv run ssm whoami --profile dev
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
