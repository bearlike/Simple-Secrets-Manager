<h1 align="center"><a href="#"><img alt="Simple Secrets Manager" src="docs/img/gh_banner.png" /></a></h1>
<p align="center">
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Tag" src="https://img.shields.io/badge/Docker-ghcr.io%2Fbearlike%2Fsimple%E2%80%94secrets%E2%80%94manager%3Alatest-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Architecture" src="https://img.shields.io/badge/architecture-arm64v8%20%7C%20x86__64-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml/badge.svg"></a>
    <a href="/LICENSE"><img alt="License" src="https://img.shields.io/github/license/bearlike/simple-secrets-manager.svg"></a>
</p>

Simple Secrets Manager is a lightweight, self-hosted secret manager for teams that need clean project/config-based secret organization without enterprise overhead. Comes with a `ssm-cli` command-line client.

<img height="720" alt="image" src="https://github.com/user-attachments/assets/539016cb-9428-4b3d-8704-31dc474caf65" />

## 🧭 Table of Contents

- [Getting Started](#-getting-started)
- [Features](#-features)
- [Documentation](#-documentation)
- [Update Existing Deployment](#-update-existing-deployment)
- [Contributing](#-contributing-)
- [Bug Reports and Feature Requests](#-bug-reports-and-feature-requests)

## 🚀 Getting Started

### 1️⃣ Deploying the SSM Server

Start the full stack with Docker Compose:

```bash
./scripts/deploy_stack.sh
```

This script reads `VERSION`, exports `APP_VERSION`, and runs `docker compose up -d --build` with deterministic image labeling.

Endpoints:

- Frontend: `http://localhost:8080`
- Backend API via proxy: `http://localhost:8080/api`
- Backend API direct: `http://localhost:5000/api`

#### First-Time Setup

On a fresh install:

1. Open `http://localhost:8080`
2. Complete initial setup (create first admin user)
3. Sign in and create projects/configs/secrets

API-only bootstrap steps are in [`docs/FIRST_TIME_SETUP.md`](docs/FIRST_TIME_SETUP.md).

---

### 2️⃣ Installing `ssm-cli` locally

`ssm-cli` is a lightweight command-line client that securely authenticates to Simple Secrets Manager and injects your project/config secrets into any command or runtime on demand.


Install `ssm-cli` globally via uv:

```bash
uv tool install git+https://github.com/bearlike/Simple-Secrets-Manager.git
uv tool update-shell
ssm-cli --help
```

If `ssm-cli` is not found, ensure uv's tool bin is on `PATH`:

```bash
export PATH="$(uv tool dir --bin):$PATH"
```

Already installed? Update to latest:

```bash
uv tool upgrade simple-secrets-manager
```

If you installed from Git and want a fresh reinstall:

```bash
uv tool install --force git+https://github.com/bearlike/Simple-Secrets-Manager.git
```

#### Authenticate CLI to Your Backend

Set backend URL and token:

```bash
ssm-cli configure --base-url http://localhost:8080/api --profile dev
ssm-cli auth set-token --token "<service-or-personal-token>" --profile dev
```

Or login with username/password:

```bash
ssm-cli login --profile dev
```

#### Use the Application from CLI

Inject secrets into a process:

```bash
ssm-cli run --profile dev -- python app.py
```

`ssm-cli run` resolves secret references by default, including `${KEY}`, `${config.KEY}`, and `${project.config.KEY}`.
Invalid or unresolved references are rejected on save by the API, and missing references at read time resolve to empty strings.

Download secrets:

```bash
ssm-cli secrets download --profile dev --format json
ssm-cli secrets download --profile dev --format json --raw
```

Write a single secret:

```bash
ssm-cli secrets set --profile dev --key API_KEY --value "super-secret"
printf '%s' "$TOKEN_VALUE" | ssm-cli secrets set --profile dev --key TOKEN --value-stdin
```

Bulk upload secrets:

```bash
ssm-cli secrets upload --profile dev --env-file .env.production
ssm-cli secrets upload --profile dev --json-file secrets.json
cat secrets.json | ssm-cli secrets upload --profile dev --stdin --format json
```

Check active CLI session:

```bash
ssm-cli whoami --profile dev
```

### 3️⃣ Authenticate and bootstrap an existing project/config

If you already have a project and config with secrets (for example `my-project` + `dev`), you can authenticate once and immediately verify secret injection.

Configure the backend and save a token:

```bash
ssm-cli configure --base-url http://localhost:8080/api --profile dev
ssm-cli auth set-token --token "<service-or-personal-token>" --profile dev
```

Set default project/config context for your current directory:

```bash
ssm-cli setup --project my-project --config dev --profile dev
```

Run a command with injected secrets and inspect a specific environment value:

```bash
ssm-cli run --profile dev -- printenv EXAMPLE_API_KEY
```

If `EXAMPLE_API_KEY` exists in your selected config, you should see its value printed from the child process environment.

---

## ✨ Features

Prioritized by customer value and typical adoption flow:

1. **Self-hosted deployment with guided bootstrap**  
   Deploy the full stack with Docker Compose and initialize the first admin account through the built-in onboarding flow.

2. **Project + environment-based secret organization**  
   Organize secrets by project and config (for example `dev`, `staging`, `prod`) with optional parent-child inheritance to reduce duplication.

3. **Secure secret lifecycle management in the Admin Console**  
   Create, edit, delete, search, and reveal secrets with a streamlined UI built for day-to-day environment management.

4. **Bulk import/export for real workflows**  
   Import `.env` files with preview and conflict awareness, and export secrets as JSON or `.env` for runtime consumption.

5. **Reference-aware secret composition**  
   Compose values with placeholders (same config, cross-config, or cross-project) and choose resolved or raw output modes when reading/exporting.

6. **Validation that prevents broken secret references**  
   Catch invalid reference syntax, unresolved links, and recursion issues during save and compare workflows before they become runtime incidents.

7. **Scoped token-based access for users and services**  
   Issue personal and service tokens with TTL and project/config scoping, then revoke tokens when access is no longer needed.

8. **Workspace RBAC with group-based project access**  
   Manage workspace roles, project roles, groups, and group mappings to enforce least-privilege access at team scale.

9. **Audit visibility for operational accountability**  
   Track API activity with filterable audit events (project/config/time) to support incident review and compliance needs.

10. **Cross-environment drift and issue detection**  
    Compare a single secret key across configs to quickly identify mismatches, missing values, and broken references.

11. **CLI-first runtime delivery and automation**  
    Inject secrets directly into processes (`ssm-cli run`), download or mount payloads, and automate secret updates in local and CI/CD workflows.

12. **Operational quality-of-life features for large secret sets**  
    Use automatic/manual secret icons and project-wide icon recompute to keep large secret catalogs easier to scan and maintain.

---

## 📚 Documentation

- CLI reference: [`docs/CLI.md`](docs/CLI.md)
- First-time setup: [`docs/FIRST_TIME_SETUP.md`](docs/FIRST_TIME_SETUP.md)
- Container runtime reference: [`docs/README_dockerhub.md`](docs/README_dockerhub.md)
- Developer docs: [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md)

## 🔄 Update Existing Deployment

If you run from this repository source:

```bash
git pull
./scripts/deploy_stack.sh
```

If you run prebuilt images only:

```bash
docker compose pull
docker compose up -d
```

---

## 🤝 Contributing 👏

We welcome contributions from the community to improve this project. Use the steps below.

1. Fork the repository and clone it to your local machine.
2. Use the pre-commit hook to automate linting and testing, catching errors early. 
3. Create a new branch for your contribution.
4. Make your changes, commit them, and push to your fork.
5. Open a pull request describing the change and the problem it solves.

## 🐞 Bug Reports and Feature Requests

If you encounter bugs or have ideas for features, open an issue on the [issue tracker](https://github.com/bearlike/Simple-Secrets-Manager/issues). Include reproduction steps and error messages when possible.

Thank you for contributing.

---

Licensed under [CC0 1.0 Universal](./LICENSE).
