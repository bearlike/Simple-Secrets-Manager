# ssm_reload — Agent Guide

> Nearest-scope guide for `ssm_reload/`. Read the [root `AGENTS.md`](../AGENTS.md)
> first for cross-cutting principles and the memory protocol. This file
> captures only what is **not obvious from the code** in this scope.
> `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

`ssm-reload` — a Watchtower-style container reloader. It watches SSM
configs and, when a config's resolved secrets change, **recreates** every
Docker container bound to that config with fresh environment. It is an
external service: it speaks only to the SSM HTTP API and the local Docker
socket, and keeps no durable state of its own.

| Module | Answers |
| --- | --- |
| `runner.py` | What fires a reconcile pass — the periodic poll AND the Docker event stream — and why are the two threads serialized behind one lock? Where do config/client/driver get wired (`build_runner`) and where does the process start/stop (`main`, SIGTERM/SIGINT)? |
| `reconcile.py` | The platform-agnostic decision loop: group units by `(project, config)`, do ONE conditional export per config, recreate only the units that diverge, report each reload. Fail-safe rules live here (skip-on-error, never fail open). |
| `driver.py` | The `ReloadDriver` Protocol — the seam the loop drives, so a Kubernetes driver can replace Docker without touching `reconcile`/`client`. |
| `docker_driver.py` | The Docker implementation: `discover` (opt-in containers), `read_binding` (parse labels), `apply` (non-destructive recreate + rollback), and the pure `build_recreate_spec` that clones a container's full runtime spec. |
| `client.py` | The two-call SSM HTTP client: `conditional_export` (`If-None-Match` → 304 or 200+ETag) and `report_reload`. Mirrors `ssm_cli/api.py` conventions but never imports `ssm_cli` (no `click`/`keyring` in a daemon). |
| `config.py` | Which env vars configure the service (`SSM_BASE_URL`, `SSM_TOKEN`, `SSM_RELOAD_POLL_INTERVAL`, `SSM_RELOAD_LABEL_PREFIX`, `DOCKER_HOST`) and which are required (fail-fast on start-up). |
| `models.py` | The driver-agnostic `Unit`/`Binding` dataclasses carried across the seam; `Unit.raw` is the driver's private handle. |
| `errors.py` | The `SsmReloadError` hierarchy; any one raised while talking to SSM means "do nothing for this config". |
| `__main__.py` | Entry point for `python -m ssm_reload`. |
| `Dockerfile` / `docker-compose.example.yml` | How the service is packaged and deployed alongside an opted-in workload. |

## Non-obvious decisions

- **Hard isolation from the backend, by design.** This package depends on
  exactly two things: the SSM **public HTTP API** and the **local Docker
  socket**. It never imports `ssm_server.api`/`ssm_server.engines`/
  `ssm_server.access` and never touches Mongo (see the `__init__.py`
  docstring). That boundary is what lets it run as a detached sidecar with
  only a scoped token and a socket bind — don't reach into the backend for
  a shortcut; add an API call instead.
- **Stateless — every durable fact lives on container LABELS + the SSM
  API.** The service holds no database, no cache, no leader election. The
  held revision is stamped on the container as `ssm.revision`; the binding
  is `ssm.config`. Because nothing is coordinated in-process, you can run
  **one instance per Docker host** across many hosts/networks with zero
  cross-instance coordination — each manages only its local daemon.
- **Recreate, never restart — the load-bearing fact.** A container's
  environment is frozen at *create* time; `docker restart` reuses the old
  env and would silently keep stale secrets. The only way to inject fresh
  env is to **re-create** the container. This is exactly why the
  Watchtower model (recreate-from-inspect) is the right shape here, and
  why `driver.apply` recreates rather than restarts.
- **Direct env injection into vanilla containers — no image changes.**
  Fresh secrets are passed as the new container's `environment`, so any
  off-the-shelf image works with no entrypoint shim or sidecar. Honest
  tradeoff: env-injected secrets are visible in `docker inspect` /
  `/proc/<pid>/environ` — this is a deliberate v1 choice, not an oversight.
- **Label control plane (Watchtower-style), and the token is NOT a
  label.** Three labels under `label_prefix` (default `ssm`):
  `ssm.enable=true` is strict opt-in — nothing is ever touched without it;
  `ssm.config=project/config` is the binding, **operator-set**;
  `ssm.revision=<etag>` is the held revision, **reloader-managed** (do not
  set it by hand). The scoped token lives on the *service* (env var
  `SSM_TOKEN`), never in a label — labels are world-readable via
  `docker inspect`.
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
  function over `docker inspect` `attrs`, replacing only `environment`
  (and stamping `ssm.revision`) while carrying over image, cmd/entrypoint,
  user, working dir, mounts, networks+aliases+IPs, published ports,
  restart policy, healthcheck, log config, caps, privileged, ulimits,
  devices, sysctls, dns, and all resource limits. WHY it must be
  exhaustive: each recreate derives from the *live* container, so any
  field it forgets is dropped permanently and the loss **compounds** on
  every subsequent reload (see Session Lessons).
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
  filtered to container `start`/`create` carrying `ssm.enable=true`, so a
  newly-deployed or redeployed container is picked up near-instantly
  instead of on the next poll tick. Both call the same idempotent
  `reconcile`; the event stream only wakes it sooner.
- **The driver seam is a `Protocol`, not an ABC.** `ReloadDriver` is
  structural so `DockerDriver` needn't inherit anything, and the loop
  type-checks against the interface. Docker is the only implementation in
  v1; a Kubernetes driver is meant to drop in behind the same three
  methods without changing `reconcile` or `client`.

## Session Lessons (Non-Trivial)

- **Dropped HostConfig fields cause cumulative drift, not a one-time
  loss.** Because every recreate rebuilds the spec from the *current*
  live container, any field `build_recreate_spec` fails to clone is gone
  for good and the next reload inherits the already-degraded container —
  the gap widens each cycle. `dns`/`sysctls`/`ulimits`/`devices`/
  `extra_hosts` were originally omitted and had to be added (see
  `_runtime_kwargs`). When you touch the spec mapping, treat a missing
  field as a silent, compounding regression, and add a
  `test_docker_driver.py` case that asserts it survives a round-trip.
- **A recreate feeds its own `create`/`start` events back into the event
  stream.** That can wake the event thread mid-recreate; if a second
  reconcile started concurrently it could collide on the `-ssmold` backup
  name. `Runner._reconcile_lock` serializes the poll thread and the event
  thread so passes never overlap. Any new trigger must go through
  `run_once` (which holds the lock), not call `reconcile` directly.
- **`docker_driver.py` still imports the SDK lazily, and that choice
  predates a since-fixed hazard.** Until the 2026-07 restructure (commit
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
