# docs — Agent Guide

> Nearest-scope guide for `docs/`. Read the [root `AGENTS.md`](../AGENTS.md) first for cross-cutting principles and the memory protocol. This file captures only what is **not obvious from the code** in this scope. `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

The human-facing documentation set for the four subproducts, plus the deprecation ledger that tracks what's scheduled for removal. `README.md` is the index GitHub auto-renders when browsing this directory.

| Doc | Covers |
| --- | --- |
| `README.md` | Documentation index — a table of every guide here with a one-line description. Keep it in sync when a guide is added, renamed, or removed. |
| `CLI.md` | `ssm-cli`/`ssm` install methods (uv tool, ephemeral `uvx`), quick start, core commands, and the four resolution-order tables (base URL, project/config, profile, token), plus skills for coding agents. |
| `CONTRIBUTING.md` | The contributor entry point: prerequisites, bootstrap, local runs (backend/frontend/CLI), quality gates & pre-commit, smoke checks, commit conventions. |
| `DEPRECATIONS.md` | The deprecation ledger — deprecated endpoints/modules, removal target, and replacement, e.g. the legacy KV API vs. `secrets_v2.py`-backed routes. |
| `FIRST_TIME_SETUP.md` | Bootstrapping a fresh deployment: onboarding-status check, first-admin bootstrap call, first sign-in, CLI install. |
| `README_dockerhub.md` | Container image quick reference — the unified image's ports, registry/tag strategy, and `docker-compose` usage; mirrors the Docker Hub/GHCR description page. |
| `SECRETS_RELOADER.md` | Product guide for `ssm-reload` — quick start, label + env-var reference, behavior/security notes, Mermaid architecture and reload-lifecycle diagrams. |
| `SERVER_INSTALLATION.md` | Deploying the server stack with Compose — deploy script vs. prebuilt images, endpoints, first-time-setup pointer, updating an existing deployment. Absorbed from the root README when it was slimmed. |

## Non-obvious decisions

- **`DEPRECATIONS.md` is the single removal ledger.** When an endpoint or module goes through the layered-deprecation flow (`@deprecated` decorator → OpenAPI `deprecated=true` → response deprecation headers → removal in a later major release — see [`../ssm_server/engines/AGENTS.md`](../ssm_server/engines/AGENTS.md) and [`../ssm_server/api/resources/AGENTS.md`](../ssm_server/api/resources/AGENTS.md)), record it here. It's the one place consumers can check what's slated for removal instead of grepping decorators across `ssm_server/engines/` and `ssm_server/api/resources/`.
- **Docs are part of the contract diff, not a follow-up.** `CONTRIBUTING.md` links `CLI.md`, and both the root `README.md` and this directory's `README.md` index link every guide here. If a change alters the CLI surface (`ssm_cli/`) or an API contract, update `CLI.md` / the relevant guide in the same change — otherwise the linked docs silently drift from the code they describe.
- **`CONTRIBUTING.md` replaced the `DEVELOPER_GUIDE.md`/`DEVELOPMENT.md` pair (2026-07) as a single contributor entry point.** The old split asked a new contributor to read two files where the second mostly deferred to the first; `CONTRIBUTING.md` now carries everything (prerequisites through commit conventions) in one document, and `README.md` is the separate, GitHub-conventional documentation index. Don't recreate the two-file split — extend `CONTRIBUTING.md` in place.

## Session Lessons (Non-Trivial)

- **Specs and plans are never committed under `docs/`.** There is currently no `docs/superpowers/` in this tree — if one reappears (or any other specs/plans directory), treat it as legacy and do not add new specs to it. Why: specs and plans are transient planning artifacts that change fast and go stale; they are tracked outside the repository, and keeping them out keeps `docs/` limited to durable, user-facing reference material that's worth reviewing in a diff.
