# ssm_server/api/resources — Agent Guide

> Nearest-scope guide for `ssm_server/api/resources/`. Read the [root `AGENTS.md`](../../../AGENTS.md) and the parent [`ssm_server/api/AGENTS.md`](../AGENTS.md) first. This file captures only what is **not obvious from the code** in this scope. `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

The endpoint layer — thin HTTP resource adapters, roughly one flask-restx namespace per concern, that parse/validate a request, call an `Engine`/`Access` collaborator, and marshal the result.

| Area | Endpoints for |
| --- | --- |
| `audit/` | Paginated audit-event querying (`GET /api/audit/events`), scoped by project/config. |
| `auth/` | Onboarding bootstrap, legacy token auth, scoped v2 tokens (service + personal), username/password register/delete. |
| `compare/` | Cross-config comparison of a single secret key within a project, with reference-resolution and issue annotation. |
| `configs/` | CRUD for configs nested under a project (`/api/projects/<slug>/configs`). |
| `projects/` | CRUD for projects, including scope-filtered listing and archive toggling. |
| `secrets/` | Config-scoped secret CRUD + export (`secrets_resource.py`), the deprecated legacy KV store (`kv_resource.py`), project icon recompute (`project_icons_resource.py`), and the `${...}` reference resolver shared by secrets and compare (`references.py`). |
| `workspace/` | Workspace-level RBAC admin: settings, members, project-member bindings, groups, group membership, IdP group mappings. |
| `meta/` | `GET /api/version` — application version only. |
| `me.py` | Current-authenticated-user profile (`GET`/`PATCH /api/me`). |
| `helpers.py` | `resolve_project_config` — shared slug→document lookup (404s via `api.abort`) used by nearly every project/config-scoped resource. |

## Non-obvious decisions

- **Boolean query-string args must use `inputs.boolean`, never `type=bool`.** Query strings are always raw text, and `bool("false")` is `True` — every `location="args"` boolean parser in this tree (`archived`, `include_parent`, `raw`, `resolve_references`, `include_revoked`, …) uses `inputs.boolean`. JSON-body booleans (`workspace/workspace_resource.py`'s `referencingEnabled`, `disabled`) can stay `type=bool` because `request.get_json()` already yields a real Python `bool` — don't "fix" those to `inputs.boolean`, and don't introduce `type=bool` on a query-string arg.
- **`secrets/kv_resource.py` is deprecated but permanent.** It's marked `@deprecated` and returns `Deprecation`/`Warning`/`Link` headers via `_with_deprecation_headers`, but the routes stay live — this is a published contract (see root `AGENTS.md` "Keep published contracts stable"). Don't remove or break it; extend the ledger in `docs/DEPRECATIONS.md` instead.
- **A resource module only takes effect once imported in `ssm_server/api/api.py`.** Namespaces register on `api.namespace(...)` as an import side effect (`api.py` imports every `*Resource` class with `# noqa: F401`, unused-import only in the sense of an explicit call). Adding a file under `ssm_server/api/resources/` and wiring its routes is not enough — it silently never mounts until `ssm_server/api/api.py` imports it.
- **Authorization is never re-implemented here.** Resources call `ssm_server.access.is_auth.with_token` / `require_token` / `require_scope` / `audit_event` and `ssm_server.access.policy.authorize` to gate and log access; the scope/RBAC logic itself lives in `ssm_server/access/`. A resource that hand-rolls a permission check instead of calling into `ssm_server.access` is a bug waiting to diverge.
- **`${...}` secret references share one resolver.** `secrets/references.py::SecretReferenceResolver` is used by both `secrets_resource.py` (get/export/put-time validation) and `compare/compare_secret_resource.py` (cross-config comparison) — cycle/depth checks and scope-gated cross-config lookups live only there, not duplicated per caller.
- **`helpers.py::resolve_project_config`** is the single place that turns a `(project_slug, config_slug)` pair into documents or a 404; nearly every project/config-scoped resource calls it instead of querying `conn.projects`/`conn.configs` directly.

## Session Lessons (Non-Trivial)

- **The secrets-export 304 branch must audit too.** In `secrets/secrets_resource.py`, the `If-None-Match` fast-path that returns `304 Not Modified` still writes the `secrets.export` audit event (with `status_code=304`), exactly like the 200 branch. WHY: the `ssm_reload/` reloader polls the export endpoint continuously and in steady state is *almost always* 304 — auditing only the 200 branch would leave the vast majority of `secrets:export` accesses unlogged, silently blinding the audit trail to the very reads that dominate. If you refactor the ETag/304 short-circuit, keep the `audit_event` call on both exits.
- **The reload endpoint is machine-only by design.** `reload/reload_resource.py` (`POST /api/reload/events`) records each applied reload as a `reload.applied` audit event via the shared `ssm_server.access.is_auth.audit_event` path — same helper every other resource uses, not a bespoke log. It gates on the `reload:report` scope, which is granted **only** through `ssm_server/access/scopes.py::DEFAULT_TOKEN_ACTION_SCOPES` (service/bootstrap tokens accept arbitrary scoped actions). It is deliberately absent from `ssm_server/engines/rbac.py`'s role maps, so no personal/role RBAC path ever grants it — the reporting endpoint is reachable by service tokens only.
