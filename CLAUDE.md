# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.

## Source of truth

**Read [`AGENTS.md`](./AGENTS.md) first — it is the authoritative baseline**
(working rules, quality commands, commit conventions, and the running list of
non-trivial engineering lessons). When inside a subtree with its own
`AGENTS.md` (e.g. [`frontend/AGENTS.md`](./frontend/AGENTS.md)), follow the
nearest one too. This file only adds a map and a few high-value pointers so
you don't re-derive them.

## Subproducts

| Area | Path | What it is |
| --- | --- | --- |
| Backend API | repo root (`Api/`, `Engines/`, `Access/`, `connection.py`, `server.py`) | Flask + flask-restx REST API. Business logic lives in `Engines/`, auth/RBAC in `Access/`, HTTP resources in `Api/resources/`. |
| CLI client | `ssm_cli/` | `ssm` / `ssm-cli` — authenticates and injects project/config secrets into commands (`ssm run -- ...`). Talks to the API over HTTP. |
| Admin console | `frontend/` | React + Vite admin UI. See `frontend/AGENTS.md`. |

## Quality gate (must pass before commit)

`./scripts/quality.sh check` runs Ruff (lint + format), targeted Pylint,
MyPy, and pytest. `line-length = 79`. Fix formatting with
`./scripts/quality.sh fix`. CI (`.github/workflows/quality.yml`) fails if the
formatter would change anything.

## Things that will bite you (see AGENTS.md “Session lessons” for the why)

- **Concurrency:** all CLI JSON writes (cache/config/credentials) go through
  `ssm_cli/fsio.py::atomic_write_text` (unique temp + `fsync` + `os.replace`).
  Never hand-roll temp-then-rename — concurrent `ssm` processes will collide.
- **No tracebacks to users:** CLI readers tolerate corrupt files, and
  `_handle_errors` degrades any unexpected exception to a clean `Error: ...`
  line. The API emits a uniform `{"message": ...}` envelope with no
  stack-trace or route-template leaks (`RESTX_ERROR_404_HELP = False`).
- **Tests need no MongoDB, but the API app does:** `tests/conftest.py`
  disables the OS keyring (its D-Bus backend can hang the suite). Importing
  `Api.core` builds `Connection()` and creates Mongo indexes eagerly, so
  HTTP-level API behaviour is verified against a throwaway `mongo` container
  or in-process `app.test_client()`, not in the hermetic CI suite.
