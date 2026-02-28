<img alt="Simple Secrets Manager" src="https://github.com/bearlike/simple-secrets-manager/raw/main/docs/img/gh_banner.png" />
<p align="center">
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Tag" src="https://img.shields.io/badge/Docker-ghcr.io%2Fbearlike%2Fsimple%E2%80%94secrets%E2%80%94manager%3Alatest-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml/badge.svg"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager"><img alt="GitHub Repository" src="https://img.shields.io/badge/GitHub-bearlike%2Fsimple--secrets--manager-blue?logo=github"></a>
</p>

# Container image quick reference

Simple Secrets Manager ships as a **single unified image** that contains:

- backend API (Flask) on port `5000`
- frontend admin console (served by Nginx) on port `8080`
- reverse proxy from `http://<host>:8080/api` to backend

## Registry and tags

Primary registry:

- `ghcr.io/bearlike/simple-secrets-manager`

Tag strategy from CI (`.github/workflows/ci.yml`):

- default branch push: `latest` + short SHA tag
- branch push: branch-ref tag + short SHA tag
- semantic tag push (`vX.Y.Z`): `X.Y.Z`, `X.Y`, `X`, and tag-ref
- manual dispatch: optional custom extra tag

## Docker Compose (recommended)

Use the repository `docker-compose.yml` directly:

```bash
./scripts/deploy_stack.sh
```

Open:

- frontend: `http://localhost:8080`
- backend via proxy: `http://localhost:8080/api`
- backend direct: `http://localhost:5000/api`

## Update Existing Docker Deployment

If using prebuilt images:

```bash
docker compose pull
docker compose up -d
```

If running from source and rebuilding locally:

```bash
git pull
./scripts/deploy_stack.sh
```

CLI from anywhere:

```bash
uv tool install git+https://github.com/bearlike/Simple-Secrets-Manager.git
uv tool update-shell
ssm-cli --help
```

## Minimal compose example

```yaml
volumes:
  mongo_data:

services:
  mongo:
    image: mongo:4
    restart: always
    environment:
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: password
    volumes:
      - mongo_data:/data/db

  ssm:
    image: ghcr.io/bearlike/simple-secrets-manager:latest
    restart: always
    depends_on:
      - mongo
    ports:
      - "8080:8080"
      - "5000:5000"
    environment:
      CONNECTION_STRING: mongodb://root:password@mongo:27017
      TOKEN_SALT: change-me
      CORS_ORIGINS: http://localhost:8080,http://127.0.0.1:8080,http://localhost:5000,http://127.0.0.1:5000
      BIND_HOST: 0.0.0.0
      PORT: 5000
```

## Environment variables

- `CONNECTION_STRING`: MongoDB URI for backend storage
- `TOKEN_SALT`: token hashing salt
- `CORS_ORIGINS`: comma-separated origins for direct backend access
- `BIND_HOST`: backend bind host (default `0.0.0.0`)
- `PORT`: backend port inside container (default `5000`)
- `VITE_API_BASE_URL`: build arg used by frontend build in Docker (default `/api`)
