# ssm_reload — Agent Guide

> Nearest-scope guide for `ssm_reload/`. Read the [root `AGENTS.md`](../AGENTS.md)
> first for cross-cutting principles and the memory protocol. This file
> captures only what is **not obvious from the code** in this scope.
> `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

`ssm-reload` — a Watchtower-style secrets service with two separate jobs:
**delivery** (render every managed config to a dotenv file consumers read at
create time) and **convergence** (recreate the containers it owns when those
secrets change). It is an external service: it speaks only to the SSM HTTP API
and the local Docker socket, and keeps no durable state of its own. In
**swarm mode** (`SSM_RELOAD_SWARM_MODE=true`) both jobs are reshaped around
Docker Swarm services instead of containers: delivery becomes a Swarm
secret/config object, and convergence becomes `docker service update`, which
Swarm itself rolls out cluster-wide — see `swarm_driver.py` and the Session
Lesson below.

| Module | Answers |
| --- | --- |
| `runner.py` | What fires a reconcile pass — the periodic poll AND the Docker event stream — and why are the two threads serialized behind one lock? Where do config/client/driver/sink get wired (`build_runner`) and where does the process start/stop (`main`, SIGTERM/SIGINT)? |
| `reconcile.py` | The platform-agnostic decision loop. `Reconciler` (driver/client/projector all injected) groups units into a `ConfigGroup` per `ConfigRef`, does ONE conditional export per config, PROJECTS it, then asks `_decide` per unit whether SSM may touch it at all — that guard order IS the safety argument. `Decision`'s named constructors (`adopt`/`wait`/`defer_to_owner`/`recreate`) say what is happening; `GroupTally` accumulates the one status report each group emits per cycle (incl. the 304 steady state). |
| `projection.py` | `Projector` — the reloader's stateful wrapper over the stateless sink: which configs are already rendered (a MISSING file forces an unconditional export), and what revision was last rendered (so a config with no container bound still gets a 304 fast path). Rendering is best-effort. |
| `driver.py` | The `ReloadDriver` Protocol — the seam the loop drives, so a Kubernetes driver can replace Docker without touching `reconcile`/`client`. |
| `docker_driver.py` | The Docker implementation: `discover` (opt-in containers + their **lifecycle** facts), `read_binding`, `read_managed_keys`, `ensure_volume`, `apply` (non-destructive recreate + rollback + netns convergence), and the pure `build_recreate_spec` that clones a container's full runtime spec while MERGING fresh secrets into its env. |
| `swarm_driver.py` | `SwarmDriver` — the Docker Swarm implementation of the same `ReloadDriver` seam, but for **services**, not containers: `discover` finds opted-in services (label lives in `Spec.Labels`, i.e. `deploy.labels`), `apply` mints an immutable secret/config object per revision and calls `service.update()` (`fetch_current_spec=True`, so untouched spec fields survive), and `gc()` prunes rotated objects nothing references any more, recomputed from live cluster state each pass. `read_env`/`read_managed_keys` are deliberately always-empty — see the Session Lesson below. |
| `client.py` | The three-call SSM HTTP client: `conditional_export` (`If-None-Match` → 304 or 200+ETag), `report_reload` (`POST /reload/events`), and `report_status` (`POST /reload/report`, the per-cycle fleet heartbeat). Mirrors `ssm_cli/api.py` conventions but never imports `ssm_cli` (no `click`/`keyring` in a daemon). |
| `config.py` | `ReloadSettings` — the ONE validated `pydantic-settings` class holding every env var the service reads; `.load()` fails fast on start-up (wrapping the pydantic error into `SsmReloadError`). Also everything that is deliberately NOT an env var: the `com.bearlike.ssm` label constants, the external-owner labels it reads but never writes, `PROJECTION_DIR`/`PROJECTION_VOLUME`, the tmpfs volume options, and `SWARM_OBJECT_PREFIX`. `DOCKER_HOST` is honored by the Docker SDK itself, not parsed here. |
| `models.py` | The driver-agnostic types carried across the seam: `ConfigRef` (the ONE parser for `project/config`), `Unit` (`raw` is the driver's private handle), `Binding`, `Dependent`, and `Lifecycle` — whose fields are each a REASON TO REFUSE a recreate, and which answers the questions about them itself (`settling_reason`, `stranded_by_recreate`) rather than letting the loop reach into its state. |
| `errors.py` | The `SsmReloadError` hierarchy; any one raised while talking to SSM means "do nothing for this config". |
| `__main__.py` | Entry point for `python -m ssm_reload`. |
| `Dockerfile` / `docker-compose.example.yml` / `docker-stack.swarm.example.yml` | How the service is packaged and deployed alongside an opted-in workload (the compose example is the worked gluetun + netns-dependent stack; the stack example is the swarm-mode equivalent). |

## Non-obvious decisions

- **SSM never takes a container away from its owner — the principle the whole
  design serves.** Delivery and convergence are separate layers *because* a
  container's env is frozen at create time: only its creator can give it
  secrets, so SSM's job is to put them where the creator reads them
  (`projection.py`), and to converge only what nobody else owns
  (`reconcile.Reconciler._decide`). Anything ambiguous is REPORTED, never
  touched. If you are adding a code path that mutates a container, the
  question to answer first is "who created this, and are they mid-deploy?"
- **Hard isolation from the backend, by design.** This package depends on
  exactly two things: the SSM **public HTTP API** and the **local Docker
  socket**. It never imports `ssm_server.api`/`ssm_server.engines`/
  `ssm_server.access` and never touches Mongo (see the `__init__.py`
  docstring). That boundary is what lets it run as a detached sidecar with
  only a scoped token and a socket bind — don't reach into the backend for
  a shortcut; add an API call instead. The two leaves it MAY import
  (`ssm_contracts`, `ssm_projection`, plus `ssm_telemetry`) import no app
  package themselves, which is what keeps the boundary honest.
- **Stateless — every durable fact lives on container LABELS + the SSM
  API.** The service holds no database, no cache, no leader election. The
  held revision is stamped on the container as `<prefix>.revision`; the
  binding is `<prefix>.config` (the label namespace is the fixed
  `com.bearlike.ssm` constant, not a knob — see the Session Lesson below).
  Because nothing is coordinated in-process, you can run
  **one instance per Docker host** across many hosts/networks with zero
  cross-instance coordination — each manages only its local daemon.
- **Recreate, never restart — and MERGE, never replace.** A container's
  environment is frozen at *create* time; `docker restart` reuses the old env
  and would silently keep stale secrets, so the only way to inject fresh env is
  to **re-create**. But the recreate must overlay the secrets on the
  container's EXISTING env: replacing it drops every app-native variable the
  container's creator set (see the Session Lesson — this shipped, and it broke
  a live workload).
- **Delivery works on vanilla images — no image changes.** Secrets reach a
  container through an `env_file` its creator names, so any off-the-shelf image
  works with no entrypoint shim or sidecar. Images that read secret *files*
  natively (`*_SECRETFILE`, `*_FILE`) can mount the same volume and skip env
  entirely. Honest tradeoff: env-delivered secrets are visible in
  `docker inspect` / `/proc/<pid>/environ` — deliberate, not an oversight.
- **Label control plane (Watchtower-style), and the token is NOT a
  label.** Four labels under the fixed `com.bearlike.ssm` reverse-DNS
  namespace (`config.py` constants): `<prefix>.enable=true` is strict opt-in —
  nothing is ever touched without it; `<prefix>.config=project/config` is
  the binding, **operator-set**; `<prefix>.revision=<etag>` is the held
  revision and `<prefix>.keys=<A,B,C>` the injected key set, both
  **reloader-managed** (do not set them by hand). The scoped token
  lives on the *service* (env var `SSM_TOKEN`), never in a label — labels
  are world-readable via `docker inspect`.
- **Non-destructive recreate with full rollback (`docker_driver.apply`).**
  The original is never destroyed until the replacement is created AND
  started: **stop → rename original aside to a backup name → create new
  under the real name → attach networks (aliases/IPs) → start → only THEN
  remove the backup.** On ANY failure the half-built new container is
  removed, the backup is renamed back and restarted (if it was running),
  and a `DriverError` is raised. Because the original keeps its OLD
  `ssm.revision` throughout, a failed recreate leaves the unit DIVERGENT —
  `reconcile` logs it, never reports it, and retries it next pass. A
  healthy container is never left worse off than it started.
- **`build_recreate_spec` must clone the FULL runtime spec.** It is a pure
  function over `docker inspect` `attrs`, merging fresh secrets into
  `environment` (and stamping `ssm.revision` + `ssm.keys`) while carrying over
  image, cmd/entrypoint, user, working dir, mounts, networks+aliases+IPs,
  published ports, restart policy, healthcheck, log config, caps, privileged,
  ulimits, devices, sysctls, dns, and all resource limits. WHY it must be
  exhaustive: each recreate derives from the *live* container, so any
  field it forgets is dropped permanently and the loss **compounds** on
  every subsequent reload — `dns`/`sysctls`/`ulimits`/`devices`/
  `extra_hosts` were originally omitted and had to be added (see
  `_runtime_kwargs`). When you touch the spec mapping, treat a missing
  field as a silent, compounding regression, and add a
  `test_docker_driver.py` case that asserts it survives a round-trip. The
  mirror hazard also exists: env the IMAGE supplies is deliberately NOT copied
  into the new container's own env (`_merge_env` subtracts it), because
  freezing the image's current defaults into the container would mean a later
  image upgrade could never change them.
- **Dedup by `(project, config)`.** `reconcile` buckets discovered units
  by their binding, so N containers sharing one config trigger exactly ONE
  conditional export per pass — not N. Recreates then run only for the
  units whose `held_revision` differs from the freshly-exported ETag.
- **Fail-safe, never fail open.** Any `SsmClientError` (network, timeout,
  non-2xx) while exporting a config skips that config and mutates nothing —
  a container is never torn down because the API blinked. A `403` is
  logged and skipped specifically, not treated as "no change".
- **Adoption = poll + Docker event stream.** `Runner` runs two triggers:
  a periodic poll (`SSM_RELOAD_POLL_INTERVAL`) and a live event stream
  filtered to container `start`/`create` carrying `<prefix>.enable=true`, so a
  newly-deployed or redeployed container is picked up near-instantly
  instead of on the next poll tick. Both call the same idempotent
  `reconcile`; the event stream only wakes it sooner.
- **The driver seam is a `Protocol`, not an ABC.** `ReloadDriver` is
  structural so `DockerDriver` needn't inherit anything, and the loop
  type-checks against the interface. Docker is the only implementation in
  v1; a Kubernetes driver is meant to drop in behind the same three
  methods without changing `reconcile` or `client`.

## Session Lessons (Non-Trivial)

- **One validated settings class per service; a raw env read elsewhere is a
  defect.** `ReloadSettings` (`config.py`) is a `pydantic-settings` model —
  every env var is a declared, validated field (`grep os.environ ssm_reload/`
  returns zero), following patterns distilled from bearlike/Grove's
  `config.py`: `frozen=True` + `validate_default=True`, explicit
  `validation_alias` matching the EXACT env var names, `SecretStr` for
  `SSM_TOKEN` (unwrapped with `.get_secret_value()` only in `build_runner`
  when constructing `SsmClient`), and a direct-construction test seam
  (`ReloadSettings(base_url=..., token=...)` via `populate_by_name=True`).
  `runner.main()` calls `ReloadSettings.load()`, which wraps a pydantic
  `ValidationError` into `SsmReloadError` so start-up fails fast with one
  clean stderr line and exit 2 — never a raw traceback. **Behavior change:**
  an invalid `SSM_RELOAD_POLL_INTERVAL` (non-numeric, `0`, negative) FAILS
  FAST via the `gt=0` constraint, where the old parser silently fell back to
  30s. `SSM_RELOAD_LOG_LEVEL` is a case-normalized
  `Literal["DEBUG","INFO","WARNING","ERROR"]`, and
  `OTEL_EXPORTER_OTLP_ENDPOINT` is injected into
  `ssm_telemetry.configure(..., endpoint=...)` from settings rather than read
  inside the telemetry leaf.
- **A recreate feeds its own `create`/`start` events back into the event
  stream.** That can wake the event thread mid-recreate; if a second
  reconcile started concurrently it could collide on the `-ssmold` backup
  name. `Runner._reconcile_lock` serializes the poll thread and the event
  thread so passes never overlap. Any new trigger must go through
  `run_once` (which holds the lock), not call `reconcile` directly.
- **`docker_driver.py` still imports the SDK lazily, and that choice
  predates a since-fixed hazard.** Until the restructure (commit
  `22593a1`), the repo root had a `docker/` config directory that could
  shadow the `docker` Python package for tools run from the repo root;
  renaming it to `deploy/` removed that shadow. The lazy import was kept
  anyway because it's independently useful: `docker_driver.py` imports the
  SDK through the `Any`-typed `_docker()` shim rather than at module top
  level, so importing the module never requires the SDK, which keeps
  `build_recreate_spec` unit-testable with no Docker present. Don't add a
  top-level `import docker` here.
- **The ETag is stored and replayed verbatim.** `conditional_export`
  keeps the raw `ETag` response header (quotes included) as the new
  revision and sends it straight back as `If-None-Match`; the reloader
  never parses or reconstructs it. The server owns the hash shape (see
  [`../ssm_server/engines/AGENTS.md`](../ssm_server/engines/AGENTS.md)) —
  treat the revision as an opaque token on this side.
- **`conditional_export` MUST pass `include_meta=false` — the server's
  default is TRUE and the export ETag covers the served representation.**
  The ETag folds in per-key metadata whenever the body
  carries it (the fix for the console's stale-304 icon bug). Omit this
  param and the reloader's revision becomes metadata-sensitive: every
  icon/description/sensitivity edit (and the `updatedAt` bump any edit
  causes) would flip the tag and RECREATE containers on pure metadata
  changes. With `include_meta=false` the tag is the value-only hash —
  byte-identical to revisions stamped before the ETag change, so fleets
  don't churn on upgrade. `tests/reload/test_client.py` pins the param.
  Mixed-version note: an OLD reloader image against a NEW server gets
  meta-inclusive tags → one (safe, non-destructive) recreate per metadata
  edit — self-heals once the reloader image updates; deliberately not
  worth a compatibility knob.
- **Compose-owned containers are ALWAYS notified, never recreated — there is
  no flag, and adding one back is a defect.** An `SSM_RELOAD_OWNED_STRATEGY`
  (`notify`/`recreate`) briefly existed to let operators keep the old
  blind-recreate behavior. It was deleted before merge: a switch between "the
  way that raced compose's deploys and wiped app-native env" and "the way that
  works" is not a safety net, it is a second code path that every future change
  has to reason about, test and document — and the only reason to reach for it
  is the behavior we just proved harmful. The same reasoning killed
  `SSM_RELOAD_PROJECTION_DIR`, `SSM_RELOAD_PROJECTION_VOLUME` and
  `SSM_RELOAD_SETTLE_SECONDS`: a value with exactly one correct setting is a
  CONSTANT (`PROJECTION_DIR`, `PROJECTION_VOLUME`,
  `Reconciler.SETTLE_SECONDS`), and `/run/ssm` + `ssm-env` are half of a
  contract the consuming compose files encode too — a knob there is just a way
  for a fleet to disagree with itself. The reloader's whole env surface is now
  five inputs plus `SSM_RELOAD_PROJECTION_CONFIGS`; if you are adding a sixth,
  it must be genuine per-deployment INPUT, not a switch between an old way and
  a new way. See the hard rule in the root `AGENTS.md`.
- **The image runs as ROOT, and reverting that breaks delivery entirely.** The
  projection volume is a root-owned tmpfs at `mode=0750` — that mode is what
  keeps projected secrets private — so a non-root uid inside the container
  cannot write into `/run/ssm` at all. The image used to `USER ssm-reload`;
  with projection, every render would have failed with `PermissionError`, on
  every config, forever. (Verified: `docker run -u 1001 -v ssm-env:/run/ssm
  alpine touch /run/ssm/x` → permission denied.) The non-root user also bought
  nothing: this service's entire job needs the Docker socket, and anything that
  can reach the socket can start a privileged container, so it is
  root-equivalent on the host whatever uid it runs as. If you want non-root
  back, you must also pin the tmpfs `uid=`/`gid=` in BOTH `TMPFS_VOLUME_OPTS`
  and every compose file that declares the volume — three places that must
  agree, to buy no isolation.
- **A best-effort side effect still has to be REPORTED — "logged and swallowed"
  is not the same as "handled".** `Projector.render` returns its error message
  rather than a bool, and `_process_group` folds it into the group's report
  (`GroupTally.projection_error`, which outranks every other outcome). Before
  that, a read-only mount or an unrenderable key logged a warning and the group
  still reported `outcome="current"` — and for a BOOTSTRAP config (no units, no
  container outcome that could go red) the fleet view showed green while no
  `env_file` had ever been written and the operator's stack could not start.
  Isolate the failure from the caller's retry path, yes; hide it from the
  operator, never.
- **`ConfigRef` is the single parser for `project/config`.** Both places that
  string arrives from outside — a container's `<prefix>.config` label and the
  `SSM_RELOAD_PROJECTION_CONFIGS` setting — call `ConfigRef.parse`, which
  rejects a non-slug at the boundary with `BindingError`. That is deliberate:
  a value like `MyApp/prod` used to survive label parsing and then fail
  pydantic validation while the cycle report was being built, aborting the
  ENTIRE pass and starving every other config, once per poll, forever. Don't
  hand-roll a `partition("/")` anywhere else.
- **The label namespace is a fixed constant, not a knob.** Labels live
  under `com.bearlike.ssm` — Docker's convention is that
  third-party object labels use the org's reverse domain to avoid
  colliding with other tools' labels. An earlier iteration exposed
  `SSM_RELOAD_LABEL_PREFIX` as a migration lever; it was removed before
  any release because nothing had shipped and a configurable prefix is
  just one more way for operators and reloaders to disagree about the
  control plane (YAGNI). `config.py` holds the single source of truth
  (`LABEL_PREFIX` + `ENABLE_LABEL`/`CONFIG_LABEL`/`REVISION_LABEL`);
  everything imports those constants. The manually-plumbed `DOCKER_HOST`
  handling was removed at the same time — `docker.from_env()` honors it
  natively, so duplicating it in `Config` was dead weight.
- **Every cycle reports, even the 304.** `reconcile` now
  accumulates one `ssm_contracts.ReloadReport` per `(project, config)`
  group per pass and POSTs it via `client.report_status` to
  `/reload/report` — the steady-state 304 path returns a report with
  `outcome="current"` and every unit listed, which is the whole point:
  the server's fleet view reflects every poll, not just recreates. **One
  POST per config group** (not per unit) keeps the server's per-config
  scope check simple. The report POST is best-effort — a failure logs a
  warning and never breaks the pass, same as `report_reload`. The reloader
  stays stateless; the report is a fresh POST each cycle, holding nothing.
- **OTel events use the Logs API with `event_name`, never the Events
  API.** `ssm_telemetry.emit_event` wraps
  `logger.emit(event_name=..., ...)` (opentelemetry-python 1.43.0). The
  older `opentelemetry.sdk._events` Events API and the stdlib
  `LoggingHandler` bridge are deprecated and the handler drops
  `event_name`, so they are avoided. Emission is a **no-op** (and the SDK
  is never imported) unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set — the
  human-readable stdlib logging is untouched (two channels, one truth).
- **The typed contract is a shared leaf, not a reloader-local
  dataclass.** The report/status wire format lives in the top-level
  `ssm_contracts` (Pydantic v2) package that BOTH the reloader and the
  server import — the single source of truth for the shape. It is a leaf:
  it imports no app package (import-linter enforces), so the reloader's
  hard isolation from the backend still holds — the coupling is the HTTP
  boundary and the shared model, nothing more. See the root `AGENTS.md`
  Session Lessons for the cross-cutting rationale.
- **Config groups are isolated per pass — one group's failure may never leak
  past its loop iteration.** `Reconciler.run` wraps each group in
  `try/except Exception` → log + continue, because a single bad unit used to
  abort the ENTIRE pass and starve every other config, once per poll, forever
  (the other half of that fix is `ConfigRef.parse` at the label boundary, see
  above). Any new per-group code path must preserve both halves.
- **`_parse_secret_map` must read the export envelope's `data` map, and a
  malformed envelope must RAISE — a drifted test fixture hid a
  secret-wiping bug.** The export wire shape is
  `{"data": {...}, "meta": {...}, "status": "OK"}` (same as `ssm_cli/api.py`
  parses), but the client once collected top-level string values — yielding
  `{"status": "OK"}` — and `driver.apply` REPLACES a container's entire
  environment with that map, so every recreate silently stripped all real
  secrets from the workload. Nothing surfaced because (a) the ETag/304
  decision path never parses the body, so steady state looked perfect, and
  (b) `test_client.py`'s 200 fixture was FLAT (`{"A": "1"}`) — the classic
  "tests pin contracts" failure: the fixture pinned a shape the live server
  never sends. Caught only by live end-to-end verification (inspecting the
  recreated container's actual env keys). Rules: the 200 fixture must stay
  envelope-shaped; parse failures raise `SsmClientError` (reconcile's
  fail-safe skips the config) rather than returning `{}`, because an empty
  map here would be injected as a container's complete env; and any change
  to the export response shape must be checked against BOTH parsers (CLI +
  reloader) in the same change.
- **The reloader is never a container's only lifecycle owner —
  adoption-by-comparison.** An opted-in container co-managed by a
  Portainer/compose stack gets recreated by its stack; the new container
  carries the operator-set `enable`/`config` labels (they live in the compose
  file) but NOT the reloader-stamped `revision` label (runtime-only, and labels
  are immutable), so `held_revision` reads `None`. Blind-recreating there meant
  one extra restart per external redeploy ("the reloader keeps restarting my
  container"). Fix: on the 200 path a unit is judged by its ACTUAL env
  (`driver.read_env`, subset comparison — app-native env never blocks) and
  ADOPTED without restart when it matches; the adopted revision is kept in
  `reconcile.AdoptionCache` (process-local, keyed by container id — recreates
  mint new ids so entries self-invalidate; pruned against discovery each
  pass; rebuilt after a reloader restart at the cost of one unconditional
  export). Env read failure → recreate (fail toward known-good secrets, never
  fail open). The old blind spot — a key DELETED from a config lingering in a
  container's env, invisible to a subset check — is closed by the
  `<prefix>.keys` label, which records exactly the keys SSM injected;
  `_env_current` refuses to adopt when one of them is stale. It stays a blind
  spot for containers SSM has never recreated (no keys label), which is
  correct: SSM must not claim to manage keys it did not put there, and their
  projected `env_file` is right anyway. Adopted units report outcome
  `current`, NOT a new literal — the server's `Literal` outcome types would
  reject an unknown string, and the console's zod schema silently degrades an
  unknown outcome to `current`, so don't add one casually.
- **Post-hoc env injection CANNOT satisfy a first boot — this is why the
  projection layer exists, and it is not a nice-to-have.** A container's env is
  set at create time and is immutable after. When an operator moves secrets out
  of their compose file into SSM (the entire point of adopting SSM), the
  container is created WITHOUT them, crashes, and only then can the reloader
  react. Verified: `docker run ... qmcgaw/gluetun` with only the app-native
  vars exits 1 on `private key is not set`. It also makes
  `depends_on: condition: service_healthy` unusable — the gate can never pass
  on a first boot. Any future "just inject it after the fact" idea hits this
  same wall; the fix is always to get the secrets to the container's CREATOR.
- **Replacing a container's env on recreate destroyed a live workload — merge
  is not a refinement, it is the bug fix.** `build_recreate_spec` used to set
  `"environment": dict(env)` where `env` was ONLY the SSM export map, so every
  variable the container got from its compose file but which the config did not
  carry was silently dropped. Config `vpn/zurich` holds 5 `WIREGUARD_*` keys;
  the workload also needs `VPN_SERVICE_PROVIDER`, `VPN_TYPE`, `TZ`, and the
  port-forwarding vars — after one recreate they were gone and gluetun died on
  `OpenVPN settings: user is empty`. It also contradicted the reloader's OWN
  adoption logic, which compares secrets as a SUBSET of the container's env
  ("app-native env never blocks") — adoption assumed a superset that recreate
  then destroyed. Merge + the `<prefix>.keys` label (so removed keys still get
  pruned) is the only shape that satisfies both.
- **`network_mode: "service:X"` is a compose-only construct, which is why the
  netns guard and the owner guard almost always fire together.** Compose stores
  it as `NetworkMode: container:<id>`, and every recreate mints a NEW container
  id — so recreating a donor leaves its dependents attached to a namespace that
  no longer exists. `discover` therefore scans ALL containers (not just opted-in
  ones) to build the donor→dependents map. `apply` carries unowned passengers
  across to the new namespace (recreating them with only their `network_mode`
  rewritten — no secrets, no labels: SSM must not acquire ownership of a
  container it merely had to move); `reconcile` REFUSES the whole recreate when
  a passenger belongs to someone else. In practice a donor with dependents is
  compose-owned anyway, so the notify path usually catches it first — the
  convergence code is for the `docker run --network container:X` case.
- **A RAM-backed projection volume is empty after a reboot, and the containers
  still hold their revision labels — so a conditional export would 304 forever
  and the file would never come back.** `Projector.needs_render` (file missing →
  force an unconditional export) is what closes that, and it is the reason the
  projector, not just the sink, is stateful. The same mechanism gives a config
  with NO container bound to it (the bootstrap case) a 304 fast path, via
  `Projector.last_revision`.
- **`Decision` carries flags, not prose to be re-parsed.** An earlier cut
  decided "is this divergence waiting on a human?" by string-matching its own
  log message. Any new guard in `Reconciler._decide` must set an explicit field
  (`adopted`, `needs_owner`, `recreate`) — a caller that re-derives meaning from
  a message string breaks the moment the message is reworded.
- **`Dockerfile`'s pip list is a hand-maintained mirror of the `reload`
  extra — keep them in lock-step.** The image deliberately
  does NOT `pip install .[reload]`: that extra resolves to
  `simple-secrets-manager[otel]`, i.e. the base package, which drags in
  `click`/`rich`/`keyring` — exactly the daemon deps this service refuses
  to ship. So it hand-lists the third-party runtime deps and `COPY`s only
  the leaf source (`ssm_reload`/`ssm_contracts`/`ssm_telemetry`). The cost
  of that choice is drift: the "settings SSOT" commit (`61e7bb3`) added
  `pydantic-settings` to the `reload` extra AND to `config.py`'s imports,
  but left it out of the Dockerfile's list — the image shipped without it
  and every container crash-looped on `ModuleNotFoundError: No module named
  'pydantic_settings'` at `config.py` import. Fix was one line
  (`"pydantic-settings>=2.0,<3.0"`). RULE: when you add a runtime dep to the
  `reload` extra in `pyproject.toml`, add it to `ssm_reload/Dockerfile` in
  the same change (and vice versa). Verify with
  `docker run --rm <img>` reaching the `Configuration error:` /
  `ReloadSettings.load()` stage — a `ModuleNotFoundError` before that line
  means a dep is missing from the image.
- **Swarm mode (`SSM_RELOAD_SWARM_MODE`) manages services, not containers —
  and that forces a different delivery mechanism, not just a different
  driver.** A container's env can be merged on recreate; a Swarm secret/config
  cannot be merged into a service's literal env at all — Swarm only ever
  mounts it as a FILE, so the workload's entrypoint must source it itself.
  `SwarmDriver.read_env`/`read_managed_keys` are deliberately hard-coded empty
  (never `{}`/`set()` from a real read) because there is nothing on the
  service spec to compare a secret's *contents* against — the adopt-by-
  comparison trick that lets container mode skip a redundant recreate simply
  does not apply here; `held_revision == new_etag` (checked before adoption is
  ever considered) is what keeps the steady state cheap instead. Swarm
  secrets/configs are also immutable and cluster-wide (not per-host), which is
  why rotation mints a brand-new object per revision instead of editing one in
  place, and why exactly ONE `ssm-reload` instance — on a manager node — may
  run per swarm: two instances would race to mint differently-named objects
  for the same revision. Verified against docker-py 7.2.0:
  `Service.update(secrets=[...], labels=...)` defaults
  `fetch_current_spec=True` and merges at the FIELD level (only the keys you
  pass override; everything else — image, command, mounts, healthcheck,
  placement, networks — comes from the live spec), so passing only
  `secrets`/`labels` is safe and does not need a hand-rolled full-spec clone
  the way the container driver's `build_recreate_spec` does. Objects this
  service minted are deleted only once `gc()` (called every pass, from live
  `service.list()` state, never persisted) finds nothing still referencing
  them — Swarm itself refuses to delete a secret still bound to a task, so
  there is no safe way to prune eagerly.
- **Two swarm-mode bugs, both from trusting a Docker asymmetry that isn't
  obvious until you hit it.** (1) `docker service ls`'s own `label` filter
  only ever inspects a service's OWN labels (`Spec.Labels`, i.e. Compose's
  `deploy.labels`) — never its task template's container labels (Compose's
  plain `labels:` under a service, without `deploy:`). Filtering `discover()`
  server-side on that label silently dropped every service opted in the
  "wrong" way, with NO error anywhere — it just looked like ssm-reload was
  ignoring the labels entirely. Fix: fetch every service unfiltered and check
  BOTH label sources in Python (`_labels()` merges them, service wins on
  conflict since that's where ssm-reload writes its own). (2) A Swarm
  **secret**'s mount directory is hard-fixed to `/run/secrets/` — `target`
  only renames the file, it never relocates it — while a **config** has no
  such restriction and accepts an arbitrary absolute path. Passing the same
  bare filename for both kinds (as an early draft did) meant secrets landed
  at the documented `/run/secrets/<file>` but configs landed at `/<file>`
  (root), contradicting the docs' claimed `/run/ssm/<file>` parity with the
  non-swarm mode. Fix: `_target()` branches on `secret_kind` — bare filename
  for secrets, `SWARM_CONFIG_MOUNT_DIR`-prefixed for configs. Neither bug
  raised an exception or showed up in logs; both were "nothing happens,
  silently" failures, which is why `test_swarm_driver.py` now asserts
  `discover()` finds a service via EITHER label placement, and asserts the
  literal mount path for each `secret_kind`, not just that `apply()` ran.
- **First-boot bootstrap for swarm mode: match by mount TARGET, not by our
  own naming prefix, when deciding what to replace.** An operator can
  pre-create a placeholder secret and reference it statically in the
  service's `secrets:` block so the file exists before ssm-reload's first
  pass (mirrors the non-swarm mode's `SSM_RELOAD_PROJECTION_CONFIGS`
  bootstrap, but there is no equivalent env-var list here since a secret
  can't be attached to a service that doesn't exist yet). For that hand-off
  to be safe, `_update_service`'s "which existing reference do I replace"
  check keys off `File.Name` (the mount target) rather than the
  `ssm-<project>-<config>-` name prefix ssm-reload itself mints — Swarm
  already forbids two references at one target, so this is also strictly
  more correct for the steady state, not just the bootstrap case.
