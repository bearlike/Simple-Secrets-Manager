# Agent Guide

If an `AGENTS.local.md` exists at the repo root (git-ignored), read it too —
it carries machine- and workflow-specific guidance that never ships.

## Purpose

Simple Secrets Manager (SSM) is a lightweight, self-hosted secret manager for
teams that want clean project/config-based secret organization without
enterprise overhead. It ships four surfaces: a Flask + flask-restx REST API
(`ssm_server/`), a `ssm` / `ssm-cli` command-line client (`ssm_cli/`), a React
admin console (`frontend/`), and the `ssm-reload` container reloader
(`ssm_reload/`). See [`README.md`](./README.md) for the full problem brief and
the getting-started flow.

Maintain context across sessions. Whenever you hit a non-trivial lesson during
implementation, write it down in the **Session Lessons (Non-Trivial)** section of
the nearest `AGENTS.md` (this file for cross-cutting lessons, the scoped file for
scoped ones). Doing this builds working memory so future sessions run faster and
smoother. Keep those notes **evergreen and dateless**: never stamp a lesson with a
calendar date, and every time you touch an `AGENTS.md` revisit its lessons —
tighten the ones worth keeping and delete the trivial or stale ones. The list is
curated, not append-only; a growing pile of dated one-offs is the failure mode we
avoid.

## Core operating rules

- Start every task by building a mental map before proposing fixes.
- Separate facts from assumptions, and keep updating both while investigating.
- Prefer direct evidence (run the code, read the real output) over inferring from a
  description.
- Keep `AGENTS.md` notes evergreen and **dateless** — write a lesson as a standing
  fact, never a timestamped log entry (see the working-memory protocol below).
- Do not push to a remote unless explicitly asked.
- Always scan related components before editing so a change stays consistent with
  the surrounding code (KISS/DRY — this is what keeps the codebase from bloating).

## Before you start (context hydration)

- Read this file and [`README.md`](./README.md) first.
- Read the deepest nested `AGENTS.md` that applies before editing files in that area
  (see “Single source of truth” below). Each scope's `AGENTS.md` carries the
  non-obvious decisions and session lessons for that scope.
- Only read local source after you have the mental map.

## Repository map (subproducts)

This is a monorepo. Each area has a nearest `AGENTS.md` you must follow when working
inside it.

| Area | Path | What it is |
| --- | --- | --- |
| Backend API | `ssm_server/` (`api/`, `engines/`, `access/`, `connection.py`, `main.py`) | Flask + flask-restx REST API. HTTP resources in `ssm_server/api/resources/`, business logic in `ssm_server/engines/`, auth/RBAC in `ssm_server/access/`. See [`ssm_server/AGENTS.md`](./ssm_server/AGENTS.md). |
| CLI client | `ssm_cli/` | `ssm` / `ssm-cli` — authenticates and injects project/config secrets into commands (`ssm run -- ...`), plus read-only discovery (`projects list`, `configs list`, `secrets keys`) and `skills install` for coding agents. Talks to the API over HTTP. |
| Reload service | `ssm_reload/` | `ssm-reload` — Watchtower-style container reloader. Recreates Docker containers with fresh env when their bound SSM config's secrets change. Talks only to the API + the local Docker socket. See [`ssm_reload/AGENTS.md`](./ssm_reload/AGENTS.md). |
| Admin console | `frontend/` | React + Vite admin UI. See [`frontend/AGENTS.md`](./frontend/AGENTS.md). |

## Project structure

| Path | Purpose |
|---|---|
| `ssm_server/` | The Flask + flask-restx API server package (`api/`, `engines/`, `access/`, `connection.py`, `main.py`). See [`ssm_server/AGENTS.md`](./ssm_server/AGENTS.md). |
| `ssm_server/api/` | Flask app factory, flask-restx wiring, serialization, error envelope. See [`ssm_server/api/AGENTS.md`](./ssm_server/api/AGENTS.md). |
| `ssm_server/api/resources/` | Thin HTTP resource adapters (one namespace per concern). See [`ssm_server/api/resources/AGENTS.md`](./ssm_server/api/resources/AGENTS.md). |
| `ssm_server/engines/` | Business logic — one engine per concern, each wrapping a Mongo collection. See [`ssm_server/engines/AGENTS.md`](./ssm_server/engines/AGENTS.md). |
| `ssm_server/access/` | Authentication + RBAC/authorization boundary. See [`ssm_server/access/AGENTS.md`](./ssm_server/access/AGENTS.md). |
| `ssm_cli/` | The `ssm` CLI client. See [`ssm_cli/AGENTS.md`](./ssm_cli/AGENTS.md). |
| `ssm_reload/` | The `ssm-reload` container reloader service. See [`ssm_reload/AGENTS.md`](./ssm_reload/AGENTS.md). |
| `ssm_contracts/` | Typed cross-service **leaf**: Pydantic v2 models for the reload report/status wire format, imported by BOTH `ssm_server` and `ssm_reload`. Imports no app package. See [`ssm_contracts/AGENTS.md`](./ssm_contracts/AGENTS.md). |
| `ssm_projection/` | Secret-delivery **leaf**: renders a `project/config` to a dotenv file in a pluggable sink (`render_dotenv`, `DirectorySink`, `atomic_write_text`), imported by BOTH `ssm_cli` and `ssm_reload` so the two emit byte-identical `env_file`s. Imports no app package. See [`ssm_projection/AGENTS.md`](./ssm_projection/AGENTS.md). |
| `ssm_telemetry/` | OpenTelemetry event-emission **leaf**: no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set, imported by BOTH the server and reloader. Imports no app package. See [`ssm_telemetry/AGENTS.md`](./ssm_telemetry/AGENTS.md). |
| `frontend/` | React + Vite admin console. See [`frontend/AGENTS.md`](./frontend/AGENTS.md). |
| `tests/` | pytest suite (`tests/{server,cli,reload,contracts,telemetry,projection}`); stub only I/O boundaries. See [`tests/AGENTS.md`](./tests/AGENTS.md). |
| `scripts/` | Quality gate, version sync, icon index, hook installer. See [`scripts/AGENTS.md`](./scripts/AGENTS.md). |
| `docs/` | Human-facing docs and the deprecation ledger. See [`docs/AGENTS.md`](./docs/AGENTS.md). |
| `deploy/` | Deployment-time config consumed by the unified Docker image (`nginx.unified.conf`, `supervisord.conf`). |
| `ssm_server/connection.py` | `Connection()` — Mongo client wiring shared by the API. |
| `ssm_server/main.py` | API entry point (`python -m ssm_server.main`). |
| `pyproject.toml` | Project + deps, managed with `uv`; base install is CLI-only, `server`/`reload`/`otel`/`all` extras layer on the rest (`server`/`reload` pull `pydantic` + `otel`); Ruff/MyPy config; `line-length = 79`. |
| `.agents/skills/` | Project-local agent skills (`SKILL.md` + `metadata.json` per skill). Not module docs. |

## Single source of truth: `AGENTS.md`, with `CLAUDE.md` as a symlink

This repo has exactly **one** instruction-file format: `AGENTS.md`. To keep tools
that look for `CLAUDE.md` working without maintaining two copies, **every `CLAUDE.md`
is a relative symlink to the sibling `AGENTS.md`**. Edit `AGENTS.md`; never edit
`CLAUDE.md` directly (it is not a real file).

Nested `AGENTS.md` files live beside the code they describe and capture what is **not
obvious from the code in that scope** — the constraint, the trade-off, the past
incident, the surprising invariant. Read the deepest one that applies before editing
there.

- Root (this file) carries cross-cutting principles, structure, and cross-cutting
  session lessons.
- A nested file does **not** restate root-level content. If a lesson is scoped to one
  package, it lives in that package's `AGENTS.md`, not here.
- When you add a new package worth documenting, add an `AGENTS.md` there and a
  sibling `CLAUDE.md` symlink (`ln -s AGENTS.md CLAUDE.md` inside the directory).
- Exception: `.agents/skills/*/AGENTS.md` are **skill** files (consumed by the skill
  loader), not module guides — do not add `CLAUDE.md` symlinks there.

## Engineering principles

These apply across every module. Some areas already follow them tightly; others are evolving. The bar isn't perfection — every change should leave the surrounding code more maintainable than it found it. Small decreases in code health compound into rewrites; small improvements compound into a codebase a new engineer can join in a week.

- **Modules align with concerns, not technical layers — Single Responsibility Principle at module scale.** The Single Responsibility Principle (Robert C. Martin) says a unit of code should have one reason to change. At module granularity: each module should answer one question, nameable in a single sentence. If you can't, it's drifting toward a junk drawer — split the concerns out, or fold the module into its real owner. Boundaries follow what changes together, not generic "models / views / controllers" buckets.
- **Public surface is small and explicit.** A package's entry point is its contract; leading underscores on internal modules and subpackages signal "don't import from here". Explicit re-export lists pin what consumers may actually depend on. The smaller the public surface, the cheaper internal refactors become.
- **Dependencies flow inward.** Orchestration layers import from utility layers; the reverse is a smell. When a low-level helper has to know about a high-level caller, the boundary is wrong — most circular-import pain traces back to this.
- **Boring code beats clever code.** Reuse the pattern already established in the project. Local cleverness has a price every reader pays; if you must deviate, name the reason inline. Predictability across modules is what keeps onboarding cheap as the team grows.
- **Add structure only when there's a real concern to separate — You Aren't Gonna Need It (YAGNI).** YAGNI, from Extreme Programming, says: build only what the current requirement demands; do not add abstraction on speculation. Three similar lines is fine. A new helper, class, or subpackage costs review surface for years — pay only when one engineer can plausibly own the new boundary, not for hypothetical future scaling. Applies to abstraction layers as much as to features.
- **No feature flags, and no knobs that keep superseded behavior alive (hard rule).** When a behavior is replaced, **delete the old one** — do not add a setting, env var, strategy literal, or `if legacy:` branch that lets an operator (or a future reader) opt back into it. Such a flag is not a safety net; it is a second code path that must be reasoned about, tested, and documented forever, and it quietly doubles the surface of every later change. The same applies to a knob nobody asked for: a value that has exactly one correct setting is a **constant**, not configuration (`LABEL_PREFIX`, `PROJECTION_DIR`, `Reconciler.SETTLE_SECONDS` are the precedents — see [`ssm_reload/AGENTS.md`](./ssm_reload/AGENTS.md)). A setting earns its existence only when it is genuine **input** that differs per deployment (a URL, a token, which configs to bootstrap), never when it is a switch between an old way and a new way. If a replaced behavior was load-bearing for someone, that is a migration note in the README and the PR body — not a flag.
- **Strong types where they catch bugs.** Narrow literal types for string sets that drive branching, structured types for conditional payload schemas, class-level constants marked as such, explicit return types everywhere. Escape-hatch types (the language's `Any` equivalent) only for genuinely heterogeneous external data, narrowed at the boundary. Introduce protocols / interfaces only when more than one real implementation exists. New cross-service/wire contracts are expressed as Pydantic v2 models in a shared leaf package rather than hand-validated dicts — `ssm_contracts` is the precedent.
- **Side effects at the edges, pure logic in the middle.** Input/output, network, database sessions, and time-of-day belong at the module boundary — request handlers, fetchers, drivers. The decision logic in between should be testable without those. Best-effort side effects must isolate their failures: bounded timeout, structured log per outcome, never re-raise into the caller's retry path.
- **Tests pin contracts, not implementation.** When a test patches a private symbol, that path becomes an implicit contract — moving it silently no-ops the patch and the test still passes. Either surface the seam publicly or update the test in the same commit. Hidden coupling between test and implementation is the most common cause of refactor friction.
- **Comments and docstrings explain WHY, not WHAT.** Names and types document the what; comments and docstrings carry the constraint, the trade-off, the past incident, the surprising invariant. Docstrings render in Integrated Development Environment (IDE) hover — write the first line for the engineer deciding whether to call this, then add Args / Returns / Raises only for things the type signature doesn't already convey.
- **Keep It Simple, Stupid (KISS) and Don't Repeat Yourself (DRY) are the core philosophy.** Bias toward less code, not more. Before writing anything custom, search for an existing library or an existing utility in the codebase. **Pattern: proven library for infrastructure, custom code only for business logic.**

### Code shape — classes and dependency injection (how we write new code)

This is the default paradigm for new code, and the one to protect. Follow a class / attribute / method structure: an **atomic class holds its state as attributes**, and its **instance methods and static methods describe the behavior over those attributes**. The class is the unit of design — a single class can represent an entire feature set, functionality, behavior, or strategy, and that cohesion is what makes the paradigm solid.

- Use **inheritance** for genuine specialization, and **dependency injection** for collaborators: pass dependencies in rather than constructing or reaching for them inside. DI is what cuts the unnecessary loops and repeated branching, and it lets a unit be tested without its real input/output.
- Reject the anti-pattern: too many private functions, or too many root-level (module-level) functions, that are hard to read because they belong to no properly-describing atomic class within their module. If a function operates on a class's state, it is a method of that class, not a free function.
- Decompose relentlessly. Files, modules, classes, and individual methods are each as atomic as possible — a small, deterministic, single-responsibility scope — yet read as tightly related to one another when expanded. High cohesion inside a unit; minimal surface between units.

> In this repo the pattern is visible in the engines: `ssm_server/engines/projects.py::Projects`,
> `ssm_server/access/tokens.py::Tokens`, etc. each hold their Mongo collection as state and
> inject collaborators (`Projects(projects_col, workspaces_engine=...)`). New backend logic
> should follow the same shape.

### Other rules

- Code validates itself at the point of definition (schema validators, strict configs that forbid unknown fields).
- **One validated settings file per deployable service is the only place environment variables are read.** Each service (`ssm_server`, `ssm_reload`) has a single `pydantic-settings` class holding every env var as a declared, validated field, built once at start-up and constructor-injected (no global accessor); a raw `os.environ`/`os.getenv` anywhere else in that service is a defect. See [`ssm_server/AGENTS.md`](./ssm_server/AGENTS.md) and [`ssm_reload/AGENTS.md`](./ssm_reload/AGENTS.md). The CLI is the deliberate exception (see [`ssm_cli/AGENTS.md`](./ssm_cli/AGENTS.md)).
- Define logic once; call everywhere — when a rule is reused by more than one caller, it lives in one place.
- Smallest diff that solves the problem. No speculative abstractions.
- Keep published contracts stable: interface names, method signatures, and field names don't move under consumers without coordination. **In this repo that specifically means API response contracts stay stable unless an explicit versioned change is requested, and legacy `/api/secrets/kv` endpoints are not removed** — deprecate in layers instead (see [`ssm_server/engines/AGENTS.md`](./ssm_server/engines/AGENTS.md)).
- Tests prefer real code paths; stub only Input/Output (I/O) boundaries. Cover full orchestration loops with in-memory fakes for external services.
- Type hints stay precise; avoid escape-hatch types.
- Gitmoji plus Conventional Commits for commit messages — format, emoji table, and examples live in [`docs/CONTRIBUTING.md` → Commit conventions](./docs/CONTRIBUTING.md#commit-conventions).
- Do not push unless explicitly asked.
- Treat Large Language Models (LLMs) and agents as non-deterministic black-box Application Programming Interfaces (APIs); avoid anthropomorphic language.

## Quality gate (must pass before commit)

`make check` is the front door; it wraps `./scripts/quality.sh check`, which
runs, in order: Ruff (lint + format check), targeted Pylint anti-pattern
checks, MyPy, import-linter, the generated env-var-reference drift check, and
pytest. `line-length = 79`. Fix formatting with
`make fix` / `./scripts/quality.sh fix`. `make precommit-install` wires the
fast pre-commit gate via `.githooks`. CI (`.github/workflows/quality.yml`)
fails if the formatter would change anything. See
[`scripts/AGENTS.md`](./scripts/AGENTS.md) for the exact Pylint codes and the
DeepSource mapping.

## Running, testing, linting

- Install: `uv sync --all-extras` (dev deps: `pytest`, `ruff`, `mypy`, plus the
  `server`/`reload` extras so the whole monorepo imports locally). A
  CLI-only install (e.g. `uv tool install`) stays lean with just the base
  dependencies — see the extras layout in `pyproject.toml`.
- Run the API: `uv run python -m ssm_server.main` (needs a live MongoDB; see
  `ssm_server/connection.py`).
- Run the CLI: `uv run ssm ...` (installed as `ssm` / `ssm-cli`).
- Backend quality gate: `make check` (or `./scripts/quality.sh check`; `make fix` / `./scripts/quality.sh fix` to auto-fix).
- Tests: `make test` / `uv run pytest -q` (hermetic; no MongoDB — see [`tests/AGENTS.md`](./tests/AGENTS.md)).
- Frontend: `make frontend` or `cd frontend && npm run lint` and `npm run build` (and `npx tsc --noEmit` — see [`frontend/AGENTS.md`](./frontend/AGENTS.md)).
- Full stack via Docker: `make stack` / `docker compose up -d --build` (or `./scripts/deploy_stack.sh`).
  - Frontend: `http://localhost:8080` · API via proxy: `http://localhost:8080/api` · API direct: `http://localhost:5000/api`.
  - Frontend reaches the backend via `VITE_API_BASE_URL` (defaults to `/api`).
  - Optional reloader sidecar: `docker compose --profile reload up -d` with
    `SSM_RELOAD_TOKEN` set — see [`docs/SECRETS_RELOADER.md`](./docs/SECRETS_RELOADER.md).

## Commit conventions

Only commit when asked. Follow the format and emoji table in
[`docs/CONTRIBUTING.md` → Commit conventions](./docs/CONTRIBUTING.md#commit-conventions).

## Session memory (working-memory protocol)

A future session will have **zero memory** of this one. This section, plus
`Session Lessons` below (and in each scoped `AGENTS.md`), is how knowledge survives.
Treat it as a first-class deliverable.

- During work, keep a running split of **facts vs assumptions**.
- The moment you learn something non-trivial (a gotcha, a hard constraint, a decision and
  its rationale, a dead end and why it failed, a key finding from research), capture it.
- Save the **distilled insight, not a pointer**. Write the conclusion and the "why", and
  the concrete fix or command if there is one. Not "see this library's docs". The next
  session must act on it without redoing the research.
- Record it in the **Session Lessons (Non-Trivial)** section of the nearest scope. Put
  cross-cutting lessons here; put scoped lessons in the scoped `AGENTS.md`. Promote a
  scoped lesson into a stable section once it becomes a standing rule, then trim the log.
- Non-trivial, reusable takeaways only. Not a play-by-play, nothing already obvious from
  the code.
- **Never date-stamp a lesson, and keep the list curated, not growing.** Write each
  lesson as an evergreen standing fact. Every time you edit an `AGENTS.md`, re-read its
  lessons and prune: tighten what still earns its place, delete anything trivial, stale,
  or now obvious from the code. A dateless, bounded list beats an append-only log that
  rots.

## Session Lessons (Non-Trivial)

> Curated working memory for **cross-cutting** lessons only — prune aggressively, never
> date-stamp. Scoped lessons live in the scoped `AGENTS.md` (linked from the Project
> structure table). Promote stable rules upward into the sections above, then remove
> them here; delete anything trivial or stale on sight.

- **`git push` is blocked by the pre-push hook when the working tree is dirty**, even
  if the dirty files are unrelated to the commit being pushed. Practical workflow:
  temporarily `git stash` unrelated local edits, push, then `git stash pop`.
- **Project-local agent skills go under `.agents/skills/<skill-name>/`** with at
  minimum `SKILL.md` plus a small `metadata.json` for discoverability. Keep `.agents/`
  as a container for `.agents/skills/` only — do not place skills directly under
  `.agents/`, and do not use `.agent/skills/`.
- **Secret hot-reload research (for `ssm_reload/`) — don't re-derive this.**
  There is **no Docker-Compose-native secret refresh**: both env vars and
  file-secrets (`/run/secrets`) are materialized only at container *create*
  time, so any auto-update is necessarily an external "detect → render →
  restart (i.e. recreate)" loop, never an in-place update. Off-the-shelf
  reload primitives fall into three interchangeable shapes — (1)
  supervise-and-restart (Doppler/Infisical `run --watch`, consul-template /
  Vault-Agent `exec`), (2) webhook-to-CD (Doppler webhooks), and (3)
  event-bus-plus-glue (GCP Pub/Sub → Cloud Run). We chose (1), the
  Watchtower recreate model. One trap to avoid: Doppler's "change a secret →
  redeploy" is delivered by its **webhooks + `run --watch`**, NOT by its GCP
  Secret Manager integration — that sync is one-way, value-only, and
  redeploys nothing, so don't model our design on the GCP-sync path.
- **Where the rest of the lessons went:** the previously-flat backend lessons now live
  in their scoped guides — CLI concurrency/error-UX in [`ssm_cli/AGENTS.md`](./ssm_cli/AGENTS.md),
  the API error envelope in [`ssm_server/api/AGENTS.md`](./ssm_server/api/AGENTS.md), test
  hermeticity in [`tests/AGENTS.md`](./tests/AGENTS.md), archiving/icons/deprecation/service-class
  patterns in [`ssm_server/engines/AGENTS.md`](./ssm_server/engines/AGENTS.md), and the
  DeepSource/Pylint mapping in [`scripts/AGENTS.md`](./scripts/AGENTS.md). Add new lessons to the
  nearest scope, not here, unless they are genuinely cross-cutting.
- **The `Api/Engines/Access` → `ssm_server/{api,engines,access}` restructure
  (commit `22593a1`) was about giving the server a home, not just
  renaming folders.** Before it, the server's four packages sat loose at the
  repo root next to the CLI and reloader with no shared namespace, and a
  repo-root `docker/` config directory shadowed the `docker` Python SDK that
  `ssm_reload/docker_driver.py` needs to import (see the historical note in
  [`ssm_reload/AGENTS.md`](./ssm_reload/AGENTS.md)) — renaming it to `deploy/`
  removed that shadow entirely. The dependency list was split at the same
  time into a lean CLI-only base plus `server`/`reload`/`all` extras
  (`pyproject.toml`), so `uv tool install` for the CLI no longer drags in
  Flask/PyMongo/Docker SDK. An import-linter boundary (wired by a parallel
  change alongside the new `Makefile`'s `lint-imports` target) now enforces
  in CI the same dependency-direction rules this file used to state only as
  prose (`Api → Engines/Access`, `ssm_reload` never importing the server
  packages) — read the linter config if a legitimate new import gets
  rejected, don't just silence it.
- **A container's environment is frozen at CREATE time — so "deliver the
  secrets to whoever creates the container" beats "fix the container
  afterwards", every time.** This is the constraint behind the split between
  `ssm_projection` (delivery: render a config to a dotenv file the creator
  reads) and `ssm_reload`'s convergence loop (recreate only what SSM itself
  owns). Post-hoc injection cannot satisfy a FIRST boot at all — the container
  comes up without its secrets, crashes, and only then can anything react — and
  a tool that recreates containers it did not create will race their real owner
  (it renamed a compose container aside mid-`compose up` and killed the deploy).
  If a future feature is tempted to mutate a running workload, ask first
  whether the same outcome can be reached by putting the right bytes where its
  creator already looks. Corollary, verified live (Compose v5.3.1 / Docker
  29.6.1): compose MERGES `env_file` with `environment` (so app-native config
  stays in git next to injected secrets) and folds the `env_file`'s CONTENTS
  into its config hash (so rewriting the file makes `docker compose up -d`
  recreate exactly the affected services, in dependency order).
- **Shared typed contracts live in a top-level leaf package, not inside a
  producer or consumer.** The reload-transparency pipeline needs
  ONE definition of the report/status wire format that both `ssm_server` and
  `ssm_reload` agree on. Putting it in either side would violate the reloader's
  hard backend-isolation (if it lived in `ssm_server`) or make the server
  import the reloader. The fix: a dedicated leaf, `ssm_contracts` (Pydantic v2,
  camelCase via `alias_generator=to_camel` + `populate_by_name`,
  `extra="ignore"` so version drift never hard-fails). Both sides import it; it
  imports no app package (import-linter enforces the leaf rule). The reloader
  builds `ReloadReport` and `model_dump(by_alias=True)`; the server
  `model_validate`s the body and dumps the response through the same models —
  one source of truth, the HTTP boundary the only coupling. The companion leaf
  `ssm_telemetry` follows the identical pattern for OTel events (Logs API +
  `event_name`, no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set), and
  `ssm_projection` for the dotenv renderer the CLI and the reloader must emit
  BYTE-IDENTICALLY (compose hashes the file's contents; two renderers that
  disagreed on key order would fight each other forever). When you need a shape
  — or an output format — shared across the import boundary, add a leaf; don't
  reach across it, and don't duplicate it.
