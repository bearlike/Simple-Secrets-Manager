# ssm_server — Agent Guide

> Nearest-scope guide for `ssm_server/`. Read the [root `AGENTS.md`](../AGENTS.md)
> first for cross-cutting principles and the memory protocol. This file
> captures only what is **not obvious from the code** in this scope.
> `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

The Flask + flask-restx REST API server package — everything that used to sit
as loose `Api/`, `Engines/`, `Access/` packages at the repo root before the
2026-07 restructure (see the root `AGENTS.md` Session Lessons) now lives under
this one namespace.

| Area | Answers | Guide |
| --- | --- | --- |
| `api/` | The HTTP boundary: app factory, flask-restx wiring, serialization, error envelope. | [`api/AGENTS.md`](./api/AGENTS.md) |
| `api/resources/` | Thin per-namespace HTTP resource adapters. | [`api/resources/AGENTS.md`](./api/resources/AGENTS.md) |
| `engines/` | Business logic — one engine class per concern, each wrapping a Mongo collection. | [`engines/AGENTS.md`](./engines/AGENTS.md) |
| `access/` | Authentication + RBAC/authorization boundary. | [`access/AGENTS.md`](./access/AGENTS.md) |
| `connection.py` | `Connection()` — the module-level singleton that constructs every engine/access class over its Mongo collection and wires their collaborators (see its `__connection.__init__`). |
| `main.py` | Entry point. `python -m ssm_server.main` calls `init_app()`, which imports `ssm_server.api.api:app` and runs the Flask dev server. |

This file stays deliberately short — it's a map to the child guides, not a
restatement of them. Read the linked `AGENTS.md` for the package you're
actually editing.

## Non-obvious decisions

- **Importing `ssm_server.api.core` has side effects.** Its module-level
  `conn = Connection()` eagerly opens Mongo and builds indexes, and
  `ssm_server.api.api` (which every resource module imports to register its
  namespace) imports `core` in turn. There is no import-only mode — anything
  that imports `ssm_server.api.api`/`ssm_server.main` needs a live MongoDB.
  This is why the hermetic `tests/` suite never imports these modules (see
  [`tests/AGENTS.md`](../tests/AGENTS.md)).
- **`ssm_server.access` depends back on `ssm_server.api.core`, by design.**
  `access/is_auth.py` does `from ssm_server.api.core import conn, api` rather
  than taking them as constructor arguments like every other class in
  `access/`. It's a known, accepted coupling (see
  [`api/AGENTS.md`](./api/AGENTS.md) "Dependency direction" and
  [`access/AGENTS.md`](./access/AGENTS.md)) — don't deepen it by adding more
  `access → api` imports, and don't "fix" it without checking both guides
  first.

## Session Lessons (Non-Trivial)

- See the root [`AGENTS.md`](../AGENTS.md) Session Lessons for the
  `Api/Engines/Access` → `ssm_server/{api,engines,access}` restructure
  rationale (server needed a home, `docker/` shadowed the `docker` SDK,
  dependency extras keep `uv tool install` CLI-light). Scoped lessons for
  each child package live in their own `AGENTS.md`, not here.
