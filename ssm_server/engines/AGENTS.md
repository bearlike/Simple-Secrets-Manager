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
| `reload_status.py` | Fleet read model for `ssm-reload`: UPSERT one heartbeat per `(project, config, instance)` with a 7-day TTL, query + `group_status` transform into the `GET /reload/status` contract (via the shared `ssm_contracts` models). |
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

- **Datetimes are timezone-aware end to end, and the Mongo client is
  `tz_aware=True`.** Every engine/access writer stores
  `datetime.now(timezone.utc)` (aware), and `connection.py` builds
  `MongoClient(..., tz_aware=True)` so read-back values are aware too. WHY the
  flag is load-bearing: without it, Mongo returns NAIVE datetimes, and the one
  Python-side comparison — token expiry in `access/tokens.py`
  (`expires_at < datetime.now(timezone.utc)`) — would compare naive-vs-aware
  and raise `TypeError`. Storage is unaffected either way (Mongo persists UTC
  millis; legacy `utcnow()` docs were UTC-valued, so aware read-back is correct
  for them too). Only Python-side comparisons/arithmetic on read-back values
  matter; Mongo-side `$gt`/`$gte` filters (token `list_tokens`, audit `since`)
  serialize the operand to BSON regardless of awareness. `serialization.py::to_iso`
  already normalizes both naive and aware to the same `...Z` string, so the
  wire shape is unchanged — there are tests pinning this
  (`tests/server/test_serialization.py`). If you ever compare a datetime read
  from Mongo against a Python `datetime`, both must be aware.
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
- **`config_export_etag` (in `secrets_v2.py`) hashes the REPRESENTATION:
  values always, `meta` only when the caller passes it.** Base
  form: a SHA-256 (first 16 hex, quoted) over the canonical JSON
  (`sort_keys`, tight separators) of the fully-**resolved** `{key: value}`
  map — post-inheritance-merge, post-`${...}`-reference resolution — and
  independent of `format`/`raw`. `meta=None` reproduces that value-only tag
  **byte-for-byte** (previously stamped reloader revisions stay valid); a
  non-None `meta` folds into the hash. The value-only tag flips when (and
  only when) a resolved value changes — **including a value inherited from
  a PARENT config** — which is what makes a cheap `If-None-Match`/304 the
  correct divergence check for `ssm_reload/` (see
  [`../../ssm_reload/AGENTS.md`](../../ssm_reload/AGENTS.md)). The
  meta-inclusive tag additionally flips on icon/sensitivity/description/
  `updatedAt` changes, because the console's response body carries those.
  The function is pure and Mongo-free — keep it that way.
- **Per-key sensitivity is default-sensitive and merges most-restrictive-wins.**
  Secret docs carry `sensitive: bool`; a **missing** field
  reads as `True` everywhere, so legacy docs stay masked and no default
  reveals anything. `put()` preserves the existing flag when the caller omits
  it (never resets) and defaults `True` on create. For an effective value the
  merge across the inheritance chain is `any(doc.get("sensitive", True))` —
  if **any** config in the chain marks the key sensitive (or leaves it
  absent), the effective value is sensitive. WHY: a child must never be able
  to *widen* the exposure of a key an ancestor hid; it may only be more
  restrictive than a non-sensitive parent. `export_config` (meta) and
  `_ConfigKeyComparisonService` (`effective.sensitive`) both compute it this
  way; `direct.sensitive` is the config's own doc flag.
- **Sensitivity, provenance, and the per-secret description live in `meta`
  ONLY, never in the value map — so the VALUE-ONLY export ETag can't flip on
  them.** `export_config` gained
  `include_provenance` (adds `meta[key].source` = slug that supplied the
  effective value, and `isInherited` vs the exported config), the meta
  `sensitive` flag, and later the free-text `description`, but none of them
  enter `merged` (the `{key: value}` map that is the base of
  `config_export_etag`). This is load-bearing for the reloader: its 304
  divergence check must react to value changes only, so metadata edits must
  leave the value-only tag byte-identical (tests pin this). The CONSOLE's
  meta-inclusive representation deliberately behaves differently — see the
  `config_export_etag` entry above and the stale-304 lesson in
  [`../api/resources/AGENTS.md`](../api/resources/AGENTS.md). `format=env`
  provenance is rendered as a `# from <config>[: <description>]` comment via
  `to_env(data, annotations)`; the annotation-free call stays byte-identical.
- **Per-secret `description` mirrors `sensitive`'s write semantics exactly.**
  One free-text annotation per secret doc, resolved by
  `_resolve_description_for_put`: explicit value wins, empty string clears,
  omitted preserves the existing doc's text (so an icon/value/sensitivity
  edit never wipes an annotation), fresh key defaults to `""`. It surfaces in
  BOTH meta builders — `_ExportAccumulator.add` (export) and `_meta_payload`
  (compare) — and any new meta field must be added to both, or the table and
  the compare dialog will disagree. It is deliberately NOT validated beyond
  being a string (operator free text), and never logged (see the log-hygiene
  rule in [`../api/resources/AGENTS.md`](../api/resources/AGENTS.md)).
- **Config delete guards inbound references, not just child configs.**
  `configs.delete` already 409s on child configs; the resource
  now also calls `SecretsV2.find_configs_referencing` before deleting and 409s
  naming the referencing `project/config` slugs. WHY: a `${cfg.KEY}` /
  `${proj.cfg.KEY}` reference to a deleted config is a dangling pointer that
  only explodes at read time. The scan is a deliberately simple regex over
  stored values (`common.REFERENCE_TOKEN_PATTERN`); a bare 2-part `${cfg.KEY}`
  counts only for secrets in the deleted config's own project, a 3-part
  `${proj.cfg.KEY}` counts from anywhere.
- **The `${...}` reference grammar has ONE home: `common.REFERENCE_TOKEN_PATTERN`.**
  It was previously compiled twice — `_REFERENCE_TOKEN_RE` here
  in `secrets_v2.py` and `PLACEHOLDER_PATTERN` in
  `api/resources/secrets/references.py` — with a comment claiming the copy was
  needed because "engines must not import api". That reasoning had the axis
  backwards: `references.py` (api) already imports `is_valid_env_key`/`is_valid_slug`
  FROM `engines.common`, so the shared pattern belongs in that same leaf and
  both sides import it (`api -> engines` is the allowed direction). Don't
  re-duplicate it "to avoid an import" — the import already exists.
- **`reload_status.py` is an UPSERT+TTL read model, deliberately not another
  append-only log.** `write_report` upserts on
  `(project_id, config_id, instance_id)`, so live cardinality is bounded to
  the fleet size (one row per reloader instance per config) no matter how
  often the reloader heartbeats. A **TTL index on `last_seen_at`
  (`STATUS_TTL_SECONDS`, 7 days)** reaps DEAD instances — a decommissioned
  host ages out on its own, so the fleet view self-heals. This is the
  explicit counter-design to `audit.py`, whose unbounded growth is a known
  gap we are not repeating. The engine stores snake_case and returns
  sanitized docs; the pure `group_status` builds the camelCase
  `GET /reload/status` shape through the shared `ssm_contracts` response
  models (`populate_by_name` validates the snake_case docs, `by_alias` dumps
  camelCase) — one source of truth for the wire shape.
- **No audit event per reload heartbeat, by design.**
  `POST /reload/report` refreshes `reload_status` but writes **no**
  `audit_event`: the reloader posts one per config every ~30 s and steady
  state is almost always a 304 "current" heartbeat, which would flood the
  audit trail. The meaningful signal — an applied recreate — still lands in
  the audit log via the untouched `POST /reload/events`
  (`reload.applied`). Keep report and events split this way.
- **Every sensitivity read surface must agree, and unknown chain = sensitive
  (adversarial-review finds).** Three fixes pin this: the compare
  service fails CLOSED when a parent chain extends beyond the (authorization-
  filtered, truncated) config set it was handed — an unseen ancestor may mark
  the key sensitive; single-secret `get()` computes the flag over the FULL DB
  chain (`_chain_effective_sensitive`) so it can never disagree with export
  meta; and `to_env` flattens CR/LF out of annotation comments because config
  descriptions are operator-editable and were able to smuggle a non-comment
  line into a provenance-annotated `.env` export. The delete guard's 409 also
  names only same-project referencing configs and collapses cross-project
  ones to a count — a `configs:write` grant proves nothing about visibility
  over other projects' slugs.
- **The icon-pack catalog is a DERIVED view over `icon_index.json`, never a
  hand-maintained list.** `secret_icons.py` gained
  `list_icon_prefixes()` / `list_icon_names(prefix)` (feeding the console's
  two-stage icon picker via `GET /api/icons/prefixes[/<prefix>/names]`). They
  do **not** add a data file or fetch anything: they group the *distinct
  slugs* already in the term index by their `prefix:name` split (the same
  `_load_index()` the resolver uses), so the catalog is exactly as complete as
  `icon_index.json` — ~124k slugs across 171 packs today, near-complete but
  not 100%, which is why the frontend keeps free-text slug entry. The grouping
  is built once per process (`_icon_pack_catalog()`, `@lru_cache`) because the
  source index is ~15 MB; the public functions return fresh lists off that
  cached immutable catalog. Regenerate the underlying data via
  `scripts/build_icon_index.py` as before — the derived view has no separate
  regeneration step and must never be edited by hand. Both endpoints gate on
  `@with_token` only (no `require_scope`, no audit event): the catalog is
  static, tenant-agnostic Iconify metadata, not secret data. **Update: the
  console no longer calls these endpoints** — its picker
  searches/browses the public Iconify API directly (see
  [`frontend/AGENTS.md`](../../frontend/AGENTS.md)), because cross-pack
  search was impossible by construction on the pack-scoped catalog. The
  endpoints stay live as a published contract (removal, if ever, follows the
  layered deprecation policy above); `icon_index.json` itself is still
  load-bearing for the server-side auto-guess (`icon_source: "auto"`) path.
