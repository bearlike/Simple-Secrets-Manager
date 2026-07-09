# Server Installation

Deploy the Simple Secrets Manager server — REST API, Admin Console, and
MongoDB — with Docker Compose.

## Prerequisites

- Docker with the Compose plugin
- Ports `8080` (frontend + API proxy) and `5000` (API direct) available

## Deploy the stack

From the repository root:

```bash
./scripts/deploy_stack.sh
```

The script reads `VERSION`, exports `APP_VERSION`, and runs
`docker compose up -d --build` with deterministic image labeling.

Prefer prebuilt images instead of building locally? See the
[container image reference](README_dockerhub.md), then:

```bash
docker compose pull
docker compose up -d
```

## Endpoints

| Endpoint | URL |
| --- | --- |
| Admin Console (frontend) | `http://localhost:8080` |
| API via proxy | `http://localhost:8080/api` |
| API direct | `http://localhost:5000/api` |

## First-time setup

On a fresh install:

1. Open `http://localhost:8080`
2. Complete initial setup (create the first admin user)
3. Sign in and create projects, configs, and secrets

Prefer to bootstrap over the API (headless / scripted installs)? Follow
the [first-time setup guide](FIRST_TIME_SETUP.md).

## Enable the secrets reloader

The root `docker-compose.yml` ships an opt-in `ssm-reload` service (image
`ghcr.io/bearlike/ssm-reload:latest`) behind the `reload` Compose profile, so
a plain `docker compose up` never starts it. Bring it up with:

```bash
SSM_RELOAD_TOKEN=<a scoped service token> docker compose --profile reload up -d
```

`SSM_RELOAD_TOKEN` maps to `SSM_TOKEN` inside the container and should be a
service token scoped to `secrets:export` (plus `reload:report` for the audit
trail). See the [secrets reloader guide](SECRETS_RELOADER.md) for the full
configuration reference.

## Update an existing deployment

Running from this repository source:

```bash
git pull
./scripts/deploy_stack.sh
```

Running prebuilt images only:

```bash
docker compose pull
docker compose up -d
```

## Next steps

- Install the CLI and inject secrets into your processes:
  [CLI guide](CLI.md)
- Keep running containers in sync with their secrets automatically:
  [Secrets reloader](SECRETS_RELOADER.md)
