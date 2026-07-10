# tests — Agent Guide

> Nearest-scope guide for `tests/`. Read the [root `AGENTS.md`](../AGENTS.md) first for cross-cutting principles and the memory protocol. This file captures only what is **not obvious from the code** in this scope. `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

The pytest suite — stub only I/O boundaries (Mongo collections, HTTP
sessions, the OS keyring) so it stays fully hermetic and runs the same on a
dev laptop as in CI. Tests are split into six packages: three mirror the
subproducts — `tests/server/` (engines, access, API-adjacent resource
logic), `tests/cli/` (`ssm_cli`), and `tests/reload/` (`ssm_reload`) — and
three mirror the shared leaf packages: `tests/contracts/` (`ssm_contracts`),
`tests/telemetry/` (`ssm_telemetry`) and `tests/projection/`
(`ssm_projection`). Test file names map roughly 1:1 to
the feature under test (`server/test_rbac.py`,
`server/test_projects_configs_crud.py`, `cli/test_cli_concurrency.py`,
`server/test_secrets_v2_icons.py`, `server/test_reload_status.py`,
`reload/test_reconcile.py`, `contracts/test_reload_contract.py`,
`telemetry/test_telemetry.py`, ...) — check the matching package/file before
adding a new one. `tests/conftest.py` holds fixtures shared across all
packages; `tests/reload/conftest.py` holds reload-only fixtures and
`tests/telemetry/conftest.py` holds an autouse fixture that tears down the
telemetry provider after each test (see `ssm_telemetry/AGENTS.md`).

## Non-obvious decisions

- Engine/Access tests pass in hand-rolled `*Stub` classes (e.g.
  `WorkspacesStub`, `MembershipsStub` in `server/test_rbac.py`) instead of a
  real or mocked Mongo collection. Why: keeps the tests fast, dependency-free,
  and focused on business logic rather than driver behavior.
- CLI tests patch `ssm_cli.main.ApiClient.<method>` or the underlying
  `requests.Session.request`, never a real network call. Why: the CLI's
  contract with the API is HTTP; stubbing at the session/client boundary
  exercises real request-building code while staying offline.

## Session Lessons (Non-Trivial)

- **For `tests/reload/`, a hermetic fake can only prove the DECISION, never the
  Docker API call — verify the driver against a real daemon before believing
  it.** The fakes in `reload/conftest.py` and `test_docker_driver.py` model
  docker-py's surface, so they happily accept create kwargs the real daemon
  would reject, and they cannot tell you whether a recreated container's
  environment actually came out right (the exact class of bug that once shipped
  a `{"status": "OK"}` env into production). The cheap, safe way to close that
  gap on this host — where Krishna's REAL stacks run on the host daemon and must
  not be touched — is a throwaway Docker-in-Docker daemon:
  `docker run -d --privileged --name e2e-dind -e DOCKER_TLS_CERTDIR= -p 12375:2375
  docker:28-dind --host=tcp://0.0.0.0:2375 --tls=false`, then drive the real
  `DockerDriver`/`Reconciler` against it with `DOCKER_HOST=tcp://127.0.0.1:12375`
  (stub only the SSM HTTP client). It gives a genuine Docker API, real compose,
  and zero blast radius. Remember `docker exec e2e-dind ...` must run against
  the HOST daemon (unset `DOCKER_HOST`), while everything inside runs against
  the dind one. **Drive the built IMAGE, not just the source**, for anything
  touching the filesystem or the daemon socket: running the driver as your own
  user on the host hides every container-user bug. That is exactly how a
  root-owned `0750` tmpfs volume the non-root image could not write to reached
  a review — `docker save img | DOCKER_HOST=<dind> docker load`, then
  `docker run --rm -v ssm-env:/run/ssm --entrypoint python <img> -c ...` proves
  it in one command.
- **Keyring can hang the whole suite.** `ssm_cli.auth` imports `keyring`,
  and on a dev workstation its default SecretService/D-Bus backend can
  block indefinitely (locked keyring, no session bus) — CI is headless and
  never hits this, so the hang is invisible there and only bites locally.
  `tests/conftest.py` has an autouse fixture that does
  `monkeypatch.setattr("ssm_cli.auth.keyring", None, raising=False)` for
  every test, forcing the deterministic file-based credential path. Don't
  remove or narrow this fixture without another way to neutralize keyring.
- **The API app can't be imported in this suite.** `ssm_server/api/core.py`
  does `conn = Connection()` at module import time, which eagerly builds
  Mongo indexes. Importing `ssm_server.api.core` or `ssm_server.api.api` (or
  `ssm_server.main`) here would require a live MongoDB, breaking
  hermeticity — no test in this directory does it. To verify HTTP-level API
  behavior, use an in-process `app.test_client()` against a throwaway
  `mongo` container or a scratch server, outside this suite — not by adding
  that import here.
- **Tests pin contracts, not implementation.** Patching a private symbol
  (e.g. `ssm_cli.main.ApiClient.upsert_secret`,
  `secret_icons_module._load_index`) turns that path into an implicit
  contract: if the code moves the symbol, the patch silently no-ops and the
  test keeps passing against the *old* behavior. Prefer patching public
  seams; if you must patch a private symbol, update the test in the same
  commit that moves it.
- **Shared raw-Mongo fakes for `tests/server/` live in
  `tests/server/fakes.py`.** Before this module existed, 15+
  local `FakeCollection`/`FakeCursor`/`FakeSecrets`/`FakeConfigs` classes
  were hand-rolled per test file with real capability drift (one
  `FakeSecrets` supported `$in`/upsert/`update_many`, a sibling copy
  supported none of it) purely because whichever test wrote it first only
  needed a subset. `fakes.py` is the *union* of every capability any of
  those fakes actually exercised, verified against the real engine call
  sites — not a speculative superset. New `tests/server/` tests **must**
  import `FakeCollection`/`FakeCursor`/`FakeSecrets`/`FakeConfigs` from
  `tests.server.fakes` rather than redeclare a Mongo fake; if a test needs a
  capability the module doesn't have, extend it there once, don't fork
  another local copy. Two categories deliberately stay out of it: (1) a
  fake whose document shape is fundamentally different and single-consumer
  (`test_kv_deprecations.py`'s path-keyed, dotted-`$set`
  `FakeKVCollection`, serving only the frozen/deprecated KV engine) — folding
  it in would force complexity into the shared module for one caller; (2)
  engine-collaborator stubs that mimic another ENGINE's public methods
  rather than a raw collection (`test_rbac.py`'s `*Stub` classes,
  `test_onboarding.py`'s `FakeUserPass`/`FakeTokens`/`FakeWorkspaces`/
  `FakeUsers`/`FakeMemberships`) — different concern, leave those local.
