# ssm_server/api — Agent Guide

> Nearest-scope guide for `ssm_server/api/`. Read the [root `AGENTS.md`](../../AGENTS.md)
> and the parent [`ssm_server/AGENTS.md`](../AGENTS.md) first for cross-cutting
> principles and the memory protocol. This file captures only what is **not
> obvious from the code** in this scope. `CLAUDE.md` here is a symlink to this
> file — edit this one.

## Responsibility

The HTTP boundary: build the Flask app, wire flask-restx, register
resources, serialize Mongo docs for JSON, and shape every error response
identically — no business logic here (that lives in `ssm_server/engines/`).

| Module | Answers |
| --- | --- |
| `core.py` | Where do `app`, `api`, and the shared `conn` (`Connection()`) come from? Who else imports them? |
| `api.py` | How does a resource module get registered? What's the CORS policy? |
| `serialization.py` | How does a raw Mongo doc (ObjectId, datetime) become JSON? |
| `versioning.py` | Where does the API's reported version number come from? |
| `errors/errors.py` | What does the API return for a 404 or an unhandled exception? |
| `resources/` | See [`./resources/AGENTS.md`](./resources/AGENTS.md) for the per-resource guide. |

## Non-obvious decisions

- **One error envelope, everywhere: `{"message": ...}`.** flask-restx's
  `api.abort(code, msg)` (used throughout `resources/`, e.g.
  `api.abort(404, "Project not found")` in `projects_resource.py`) already
  emits this shape. `errors/errors.py`'s Flask-level `@app.errorhandler`
  fallbacks for 404 and uncaught `Exception` were deliberately written to
  match it, rather than the `{"error": ...}` shape they previously used.
  Both `ssm_cli/api.py::_error_message` and `frontend/src/lib/api/errorToast.ts`
  read `message` first, falling back to `error`/`status` only for
  responses that don't come from this API. Don't introduce a third shape.
- **`RESTX_ERROR_404_HELP = False`** (`core.py`) is load-bearing, not a
  cosmetic default. Left on, flask-restx appends "did you mean `<route
  template>`" to every 404 body, which leaks internal URL patterns and
  buries a clean message like "Project not found" under noise. Keep it off.
- **Importing `ssm_server.api.core` has side effects — there is no
  import-only mode.** The module-level `conn = Connection()` eagerly opens
  Mongo and creates indexes at import time. Anything that imports
  `ssm_server.api.core` (or `ssm_server.api.api`, which imports it) needs a
  live Mongo, which is why HTTP-level API tests run against a throwaway
  `mongo` container or an in-process `app.test_client()`, never the
  hermetic CI suite.
- **Registering a resource = importing it in `api.py`.** Each resource
  module registers its namespace on `api` as an import side effect;
  `api.py` imports every one of them for exactly this reason (hence the
  `# noqa: F401` on each). A new resource file that isn't imported here
  is dead code — it never gets mounted.
- **Always serialize through `serialization.py`.** `sanitize_doc` /
  `oid_to_str` / `to_iso` exist because `ObjectId` and `datetime` aren't
  JSON-native; hand-rolling `str()` conversions per-resource would drift.
  Note the casing split this sits next to: Mongo/storage stays snake_case
  (`created_at`), the API's JSON is camelCase (`createdAt`) — see
  [`../engines/AGENTS.md`](../engines/AGENTS.md) for where that mapping
  happens. A single-word field like `archived` sidesteps the split entirely,
  which is why it can look inconsistent at a glance.
- **Dependency direction is `ssm_server.api` → `ssm_server.engines`/`ssm_server.access`,
  with one exception.** `ssm_server/access/is_auth.py` imports `conn` and
  `api` back from `ssm_server.api.core` (`from ssm_server.api.core import
  conn, api`) rather than the other way around. This is a known, accepted
  coupling — don't deepen it by adding more `access → api` imports.

## Session Lessons (Non-Trivial)

- The error envelope used to be inconsistent: some fallback paths returned
  `{"error": ...}` while flask-restx's own `abort()` returns
  `{"message": ...}`. Consumers (CLI, frontend) only checked one key each,
  so the mismatch silently produced blank or generic error text instead of
  the real server message. The fix was to align every fallback in
  `errors/errors.py` to the `message` key flask-restx already uses, not to
  teach every consumer to check both keys — one canonical shape at the
  source beats defensive parsing at every call site.
