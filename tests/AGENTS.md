# tests — Agent Guide

> Nearest-scope guide for `tests/`. Read the [root `AGENTS.md`](../AGENTS.md) first for cross-cutting principles and the memory protocol. This file captures only what is **not obvious from the code** in this scope. `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

The pytest suite — stub only I/O boundaries (Mongo collections, HTTP
sessions, the OS keyring) so it stays fully hermetic and runs the same on a
dev laptop as in CI. Tests are split into three packages that mirror the
subproducts: `tests/server/` (engines, access, API-adjacent resource logic),
`tests/cli/` (`ssm_cli`), and `tests/reload/` (`ssm_reload`). Test file names
map roughly 1:1 to the feature under test (`server/test_rbac.py`,
`server/test_projects_configs_crud.py`, `cli/test_cli_concurrency.py`,
`server/test_secrets_v2_icons.py`, `reload/test_reconcile.py`, ...) — check
the matching package/file before adding a new one. `tests/conftest.py` holds
fixtures shared across all three packages; `tests/reload/conftest.py` holds
reload-only fixtures.

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
