# Deprecations

This file tracks APIs and modules that are deprecated and scheduled for
removal in a future release.

## Deprecated now

### Legacy KV API

- Status: Deprecated
- Removal target: Next major release
- Endpoints:
  - `GET /api/secrets/kv/<path>/<key>`
  - `POST /api/secrets/kv/<path>/<key>`
  - `PUT /api/secrets/kv/<path>/<key>`
  - `DELETE /api/secrets/kv/<path>/<key>`
- Legacy backend engine: `Engines.kv.Key_Value_Secrets`
- Replacement:
  - `PUT /api/projects/<project_slug>/configs/<config_slug>/secrets/<key>`
  - `GET /api/projects/<project_slug>/configs/<config_slug>/secrets/<key>`
  - `DELETE /api/projects/<project_slug>/configs/<config_slug>/secrets/<key>`
  - `GET /api/projects/<project_slug>/configs/<config_slug>/secrets?format=json|env`

## Not deprecated in this pass

- `/api/auth/tokens/` remains in use by CLI login flow and is not part of
  this removal candidate set yet.
