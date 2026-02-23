<h1 align="center"><a href="#"><img alt="Simple Secrets Manager" src="docs/img/gh_banner.png" /></a></h1>
<p align="center">
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Tag" src="https://img.shields.io/badge/Docker-ghcr.io%2Fbearlike%2Fsimple%E2%80%94secrets%E2%80%94manager%3Alatest-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Architecture" src="https://img.shields.io/badge/architecture-arm64v8%20%7C%20x86__64-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml/badge.svg"></a>
    <a href="/LICENSE"><img alt="License" src="https://img.shields.io/github/license/bearlike/simple-secrets-manager.svg"></a>
</p>

Simple Secrets Manager is a lightweight, self-hosted secret manager for teams that need clean project/config-based secret organization without enterprise overhead. Comes with a `ssm-cli` command-line client.

<img height="720" alt="image" src="https://github.com/user-attachments/assets/539016cb-9428-4b3d-8704-31dc474caf65" />

## Getting Started

### 1️⃣ Deploying the SSM Server

Start the full stack with Docker Compose:

```bash
docker compose up -d --build
```

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

Download secrets:

```bash
ssm-cli secrets download --profile dev --format json
```

Check active CLI session:

```bash
ssm-cli whoami --profile dev
```

---

## Documentation

- CLI reference: [`docs/CLI.md`](docs/CLI.md)
- First-time setup: [`docs/FIRST_TIME_SETUP.md`](docs/FIRST_TIME_SETUP.md)
- Container runtime reference: [`docs/README_dockerhub.md`](docs/README_dockerhub.md)
- Developer docs: [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md)

## Update Existing Deployment

If you run from this repository source:

```bash
git pull
docker compose up -d --build
```

If you run prebuilt images only:

```bash
docker compose pull
docker compose up -d
```

---

## Contributing 👏

We welcome contributions from the community to improve Meeseeks. Use the steps below.

1. Fork the repository and clone it to your local machine.
2. Use the pre-commit hook to automate linting and testing, catching errors early. 
3. Create a new branch for your contribution.
4. Make your changes, commit them, and push to your fork.
5. Open a pull request describing the change and the problem it solves.

## Bug Reports and Feature Requests 🐞

If you encounter bugs or have ideas for features, open an issue on the [issue tracker](https://github.com/bearlike/Simple-Secrets-Manager/issues). Include reproduction steps and error messages when possible.

Thank you for contributing.

---

Licensed under [CC0 1.0 Universal](./LICENSE).
