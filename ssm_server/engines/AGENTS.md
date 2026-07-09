# ssm_server/engines — Agent Guide

> Nearest-scope guide for `ssm_server/engines/`. Read the [root `AGENTS.md`](../../AGENTS.md)
> and the parent [`ssm_server/AGENTS.md`](../AGENTS.md) first for cross-cutting
> principles and the memory protocol. This file captures only what is **not
> obvious from the code** in this scope. `CLAUDE.md` here is a symlink to this
> file — edit this one.

## Responsibility

The business-logic core — one engine class per concern, each wrapping a Mongo
collection held as instance state.

| Module | Answers |
| --- | --- |
| `workspaces.py` | Workspace CRUD, default-workspace bootstrap, per-workspace settings (`defaultWorkspaceRole`, `defaultProjectRole`, `referencingEnabled`). |
| `users.py` | User records: create/ensure/update profile, disable/enable, delete. |
| `memberships.py` | Workspace-membership and project-membership documents (user or group subject), the raw many-to-many join tables RBAC reads. |
| `groups.py` | Groups, group membership, and external group→group mappings (SCIM/SSO-style, `provider="manual"` only today). |
| `rbac.py` | Resolves a username into an actor context: workspace role, visible project ids, and per-scope action lists. The authorization brain. |
| `projects.py` | Project CRUD, slug validation, archive/unarchive, listing with archive filtering. |
| `configs.py` | Config CRUD under a project, parent/child inheritance chain, cycle detection on reparenting. |
| `secrets_v2.py` | Config-scoped secret get/put/delete, cross-config key comparison, config export (with inheritance merge), icon-slug bookkeeping. |
| `secret_icons.py` | Pure functions that guess/validate/resolve an icon slug for a secret key from the precomputed term index. |
| `icon_index.json` | Precomputed `{term: {slug, count}}` index consumed by `secret_icons.py`; regenerate via `scripts/build_icon_index.py`. |
| `compare_issues.py` | Issue codes/builders for the config-comparison and reference-validation views (no engine state). |
| `audit.py` | Append-only audit event log: write + paginated/filtered query by project/config slug or legacy id. |
| `kv.py` | Legacy path-keyed KV secret store, fully `@deprecated` — superseded by `secrets_v2.py`. |
| `versioning.py` | Reads the installed package/`VERSION` file for the API's reported app version. |
| `common.py` | Shared `SLUG_PATTERN` / `ENV_KEY_PATTERN` validators (`is_valid_slug`, `is_valid_env_key`). |

## Non-obvious decisions

- Engines follow a class-holds-collection-as-state pattern; each `__init__`
  **eagerly** calls `create_index(...)`, so just instantiating an engine
  needs a live Mongo connection (no lazy index creation). Public engine
  methods generally return a `(payload, status_code)` tuple (or
  `(payload, message, status_code)` where a message is meaningful) that the
  `ssm_server/api/` layer consumes almost verbatim.
- `rbac.py`'s `PROJECT_ROLE_ACTIONS` / `WORKSPACE_ROLE_GLOBAL_ACTIONS` maps
  and `ssm_server/access/scopes.py`'s `DEFAULT_TOKEN_ACTION_SCOPES` list must
  stay in sync on the literal action strings (`"projects:read"`,
  `"secrets:write"`, etc.) — add a new action string in both places, or a
  role/token can silently never be granted it.
- `common.py` centralizes `SLUG_PATTERN` (`^[a-z0-9_-]+$`) and
  `ENV_KEY_PATTERN` (`^[A-Z0-9_]+$`); validate slugs/env keys through
  `is_valid_slug`/`is_valid_env_key` instead of re-rolling a regex per
  engine — `kv.py` predates this and still hand-rolls its own pattern, which
  is one more reason it's frozen/deprecated rather than extended.
- `configs.py` and `secrets_v2.py`'s comparison/export paths detect parent
  cycles by walking `parent_config_id` with a `visited` set rather than
  trusting the write path alone — reparenting is validated on write
  (`_would_create_cycle`), but read paths re-check because historical data
  or direct DB edits could otherwise infinite-loop the walk.

## Session Lessons (Non-Trivial)

- **Project archiving**: projects carry a single `archived` boolean (one
  word, so it's identical in Mongo snake_case and the API's camelCase,
  sidestepping the `created_at`/`createdAt` split). Filtering by archive
  state lives **only** in `projects.py::list()`, applied in Python after the
  Mongo fetch: `archived=True` keeps `doc.get("archived") is True`; the
  default keeps `is not True` so legacy/missing-field docs count as active.
  This filter is deliberately *not* pushed into `list_docs`/`list_by_ids` —
  `rbac.py` calls those directly to build the actor's visible-project set,
  and it needs **all** projects (including archived) or archived projects
  would silently drop out of authorization/visibility. The API parses
  `?archived=<bool>` with `inputs.boolean` (never `type=bool`, which treats
  any non-empty string as truthy). Archive/unarchive reuses the single
  partial-update path, `update(slug, name=None, archived=None)` — passing
  only `archived` toggles just that field.
- **Secret icon lifecycle**: secrets carry `icon_source` (`"auto"` or
  `"manual"`, tracked in `secrets_v2.py`, normalized by
  `_normalize_icon_source`). A project-wide icon recompute
  (`recompute_project_icon_slugs`) rewrites only keys where every doc's
  source is `auto`, so an explicit manual override on any config in the
  project protects that key everywhere. `secret_icons.py` itself is
  side-effect-free — it resolves a slug deterministically from the
  precomputed `icon_index.json` term index; regenerate that file via
  `scripts/build_icon_index.py` after changing icon-matching rules, since
  `secret_icons.py` never rebuilds it at runtime.
- **Legacy-API removal happens in layers, never a hard delete**: code-level
  `@deprecated` (see `kv.py`, using `warnings.deprecated`) → OpenAPI
  `deprecated=true` on the resource → API response deprecation headers →
  actual removal only in a later major release. `kv.py` is the reference
  example — every public method is individually decorated, not just the
  class.
- For complexity-heavy logic, prefer a module-private per-use-case service
  class with small single-purpose methods (e.g. `_ConfigKeyComparisonService`
  in `secrets_v2.py`, `_IconSlugResolutionService` in `secret_icons.py`),
  while keeping the public engine method's signature and response shape
  unchanged — it isolates the complexity without leaking it into the
  Api-facing contract.
- **`config_export_etag` (in `secrets_v2.py`) hashes VALUES, not the
  representation.** It is a SHA-256 (first 16 hex, quoted) over the
  canonical JSON (`sort_keys`, tight separators) of the fully-**resolved**
  `{key: value}` map — post-inheritance-merge, post-`${...}`-reference
  resolution. It is deliberately independent of `format` / `include_meta` /
  `raw`: no metadata, timestamps, or ordering enter the hash, so every
  export representation of the same value-set yields the same tag, and the
  tag flips when (and only when) a resolved value changes — **including a
  value inherited from a PARENT config**. That value-only stability is what
  makes a cheap `If-None-Match` / 304 the correct divergence check for the
  `ssm_reload/` service (see [`../../ssm_reload/AGENTS.md`](../../ssm_reload/AGENTS.md)).
  The function is pure and Mongo-free — keep it that way.
