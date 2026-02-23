<h1 align="center"><a href="#"><img alt="Simple Secrets Manager" src="docs/img/gh_banner.png" /></a></h1>
<p align="center">
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Tag" src="https://img.shields.io/badge/Docker-ghcr.io%2Fbearlike%2Fsimple%E2%80%94secrets%E2%80%94manager%3Alatest-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Architecture" src="https://img.shields.io/badge/architecture-arm64v8%20%7C%20x86__64-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml/badge.svg"></a>
    <a href="/LICENSE"><img alt="License" src="https://img.shields.io/github/license/bearlike/simple-secrets-manager"></a>
</p>

Simple Secrets Manager is a lightweight, self-hosted secrets platform with:

- Backend API
- Frontend Admin Console
- `ssm-cli` command-line client

## Install the Product (Backend + Frontend Bundle)

Start the full stack with Docker Compose:

```bash
docker compose up -d --build
```

Endpoints:

- Frontend: `http://localhost:8080`
- Backend API via proxy: `http://localhost:8080/api`
- Backend API direct: `http://localhost:5000/api`

## First-Time Setup

On a fresh install:

1. Open `http://localhost:8080`
2. Complete initial setup (create first admin user)
3. Sign in and create projects/configs/secrets

API-only bootstrap steps are in [`docs/FIRST_TIME_SETUP.md`](docs/FIRST_TIME_SETUP.md).

## Install CLI Once, Run Anywhere

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

## Authenticate CLI to Your Backend

Set backend URL and token:

```bash
ssm-cli configure --base-url http://localhost:8080/api --profile dev
ssm-cli auth set-token --token "<service-or-personal-token>" --profile dev
```

Or login with username/password:

```bash
ssm-cli login --profile dev
```

## Use the Application from CLI

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
