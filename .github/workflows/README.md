# GitHub workflows

CI/CD for the monorepo. Two container images ship from here:
`ghcr.io/bearlike/simple-secrets-manager` (unified server + Admin
Console) and `ghcr.io/bearlike/ssm-reload` (the secrets reloader).

> This file deliberately lives in `workflows/`, not at `.github/README.md`
> — GitHub renders `.github/README.md` as the repository front page,
> overriding the root `README.md`.

| Workflow | Trigger | What it does |
| --- | --- | --- |
| [`quality.yml`](quality.yml) | Pull requests, manual | The backend quality gate (Ruff, targeted Pylint, MyPy, import-linter, pytest) — the same checks as `make check`. Fails if the formatter would change anything. |
| [`ci.yml`](ci.yml) | Pull requests and pushes touching build-relevant paths | Builds both Docker images (matrix) to prove the delivery pipeline stays green. No pushes to a registry. |
| [`publish.yml`](publish.yml) | Push to `main`, `v*` tags, manual | Builds and publishes both images to GHCR with release tags (matrix over the two images). |
| [`publish-preview.yml`](publish-preview.yml) | Manual (`workflow_dispatch`) | Publishes branch-tagged preview images of both containers to GHCR for testing ahead of a release. |
| [`codeql-analysis.yml`](codeql-analysis.yml) | Pushes/PRs to `main`, weekly cron | GitHub CodeQL static analysis over the Python codebase. |

Conventions:

- Path filters in `ci.yml` mirror what actually feeds the images
  (`Dockerfile`, `deploy/`, `frontend/`, `ssm_server/`, `ssm_cli/`,
  `ssm_reload/`, `ssm_contracts/`, `ssm_telemetry/`, packaging files).
  Adding a new package that ships in an image means updating those
  filters too.
- The local pre-commit hook (`make precommit-install`) runs a fast subset
  of `quality.yml`; CI remains the authoritative gate.
- Versioning is driven by the `VERSION` file (checked by
  `scripts/version_sync.py`), so tag pushes and image tags stay in sync.
