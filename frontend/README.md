# SSM Admin Console

Vite + React admin UI for Simple Secrets Manager.

This app is vendored into the `Simple-Secrets-Manager` monorepo under `frontend/`.

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```
2. Set backend API base URL (optional if backend runs on `http://localhost:5000/api`):
   ```bash
   echo "VITE_API_BASE_URL=http://localhost:5000/api" > .env.local
   ```
3. Start the frontend:
   ```bash
   npm run dev
   ```
4. Open the app and sign in with a backend token.

## Docker

Build image:

```bash
docker build -t ssm-admin-console:local .
```

Run image:

```bash
docker run --rm -p 8080:80 ssm-admin-console:local
```

## Backend Connectivity

The frontend API client uses:

- `VITE_API_BASE_URL` when set
- otherwise defaults to `http://localhost:5000/api`

All API calls are made relative to that base and include `Authorization: Bearer <token>` when logged in.

## Local Backend + Frontend Workflow

1. Start `Simple-Secrets-Manager` backend (branch `feat/v1.2.0`) on `localhost:5000`.
2. Confirm backend routes are available under `/api`.
3. Start this frontend with `npm run dev`.
4. In browser, log in with a valid token and verify:
   - projects/configs/secrets load
   - create/update/delete secrets works
   - JSON and `.env` exports work
   - audit events load from `/audit/events`
   - token create/revoke works with `/auth/tokens/v2/*`
