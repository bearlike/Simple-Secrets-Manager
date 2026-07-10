# ssm_server — Agent Guide

> Nearest-scope guide for `ssm_server/`. Read the [root `AGENTS.md`](../AGENTS.md)
> first for cross-cutting principles and the memory protocol. This file
> captures only what is **not obvious from the code** in this scope.
> `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

The Flask + flask-restx REST API server package — everything that used to sit
as loose `Api/`, `Engines/`, `Access/` packages at the repo root before the
restructure (see the root `AGENTS.md` Session Lessons) now lives under
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

- **One settings file, read once, injected everywhere: `settings.py` →
  `ServerSettings`.** Every environment variable the server honors
  (`CONNECTION_STRING`, `TOKEN_SALT`, `CORS_ORIGINS`, `DEBUG`, `BIND_HOST`,
  `PORT`, `OTEL_EXPORTER_OTLP_ENDPOINT`) is a declared, validated field on this
  one `pydantic-settings` model — a raw `os.environ`/`os.getenv` anywhere else
  in `ssm_server/` is a defect (`grep` returns zero). It is a LEAF (imports
  nothing from `ssm_server`) so the hermetic suite can import and unit-test it
  without Mongo. `ServerSettings` is built exactly ONCE, at `api/core.py`
  module scope, and injected: `settings = ServerSettings()` (fail-fast) →
  `conn = Connection(settings)` → `Tokens(..., token_salt=settings.token_salt)`
  (which fixed the old DI violation where `Tokens` reached into `os.environ`
  itself). `api.py` reads `settings.cors_origins_list` from `core`; `main.py`
  reads host/port/debug and the OTel endpoint from it. There is deliberately
  NO `get_settings()`/`lru_cache` global accessor — one immutable object,
  constructor-injected.
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

- **The per-service settings file exists because a scattered config surface
  let an unwanted knob ship unnoticed.** The fix is one
  validated `pydantic-settings` class per deployable service (`ServerSettings`
  here); design decisions were distilled from bearlike/Grove's `config.py`:
  **pydantic-settings over a hand-rolled env cascade** (two layers only —
  model defaults, then env/`.env`; Grove's multi-file cascade solves a
  per-developer-repo problem we don't have); **`frozen=True` +
  `validate_default=True`**, fields declared with explicit `validation_alias`
  matching the EXACT existing env var names (the operator contract must not
  move) and `Field` constraints (`ge`/`le`) over custom validators;
  **`SecretStr` for secrets** (`TOKEN_SALT`) so no repr/log leaks them, unwrapped
  with `.get_secret_value()` only at the single point of use (token hashing);
  **settings-object DI over a global accessor** — no `get_settings()`/`lru_cache`;
  **direct-construction test seam** — `ServerSettings(_env_file=None, **kwargs)`
  (needs `populate_by_name=True`) so unit tests bypass the environment.
  Behavior deltas worth remembering: `PORT`/`DEBUG` are now *validated* (a
  non-numeric `PORT` fails fast instead of reaching Flask raw), and the
  undocumented, unused, buggy `PASSWORD_POLICY_*` env overrides were DELETED —
  their values arrived as `str` and the numeric comparisons in
  `userpass._password_policy.check()` would have `TypeError`d the moment anyone
  set one; the defaults `(6,1,1,1,1)` are now hardcoded class constants.
- **Import-order constraint: settings must be validated before `Connection`,
  at `core.py` module scope.** `core.py` does
  `settings = _load_settings()` (which wraps a pydantic `ValidationError` into a
  clean one-line loguru error and `sys.exit`s non-zero — never a raw traceback)
  BEFORE `conn = Connection(settings)`, because `Connection.__init__` opens
  Mongo immediately. `settings.py` is a LEAF (imports nothing from
  `ssm_server`) precisely so this ordering can't create an import cycle and the
  hermetic suite can import it without Mongo. `python-dotenv`/`load_dotenv()`
  and the local `strtobool` were removed: `SettingsConfigDict(env_file=".env")`
  loads the dotenv (via pydantic-settings' own `python-dotenv` dep) and pydantic
  parses booleans.
- See the root [`AGENTS.md`](../AGENTS.md) Session Lessons for the
  `Api/Engines/Access` → `ssm_server/{api,engines,access}` restructure
  rationale (server needed a home, `docker/` shadowed the `docker` SDK,
  dependency extras keep `uv tool install` CLI-light). Scoped lessons for
  each child package live in their own `AGENTS.md`, not here.
