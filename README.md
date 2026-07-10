<h1 align="center"><a href="#"><img alt="Simple Secrets Manager" src="docs/img/gh_banner.png" /></a></h1>
<p align="center">
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Tag" src="https://img.shields.io/badge/Docker-ghcr.io%2Fbearlike%2Fsimple%E2%80%94secrets%E2%80%94manager%3Alatest-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/pkgs/container/simple-secrets-manager"><img alt="Docker Image Architecture" src="https://img.shields.io/badge/architecture-arm64v8%20%7C%20x86__64-blue?logo=docker"></a>
    <a href="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/bearlike/simple-secrets-manager/actions/workflows/ci.yml/badge.svg"></a>
    <a href="/LICENSE"><img alt="License" src="https://img.shields.io/github/license/bearlike/simple-secrets-manager.svg"></a>
</p>

Simple Secrets Manager is a lightweight, self-hosted secret manager for homelabs and small teams — clean project/config-based secret organization without enterprise overhead. One container runs the server and Admin Console, `ssm-cli` injects secrets into any process, and the optional `ssm-reload` service keeps your running containers in sync when secrets change.

<!-- Images: use a strict width + height pair that matches the image's
     natural aspect ratio, so fixed sizing never skews the render. -->
<img width="830" height="312" alt="Simple Secrets Manager Admin Console" src="https://github.com/user-attachments/assets/539016cb-9428-4b3d-8704-31dc474caf65" />

## 💡 Motivation

My homelab grew past the point where I could keep secrets straight by hand. I run Kubernetes clusters and Docker containers and a stack of services that all need the same values kept in sync. The servers underneath need their own secrets too. Keeping everything rotating consistently across all of it was a nightmare. There was no lightweight way for me to configure and share secrets quickly and still keep an audit of who touched what. So I built one. And in the era of coding agents I also wanted every agent audited and pointed at exactly the config it is allowed to use.

## ✨ Features

| Feature | What it does | Guide |
| --- | --- | --- |
| 🗂️ **Projects, configs & inheritance** | Organize secrets by project and environment such as `dev`, `staging`, and `prod`. Child configs inherit from their parent and override only the values that differ. | 📖 [First-time setup](docs/FIRST_TIME_SETUP.md) |
| 🔗 **Secret references** | Compose values from placeholders like `${KEY}`, `${config.KEY}`, and `${project.config.KEY}`. Invalid, unresolved, and circular references are rejected at save time. | 📖 [CLI guide](docs/CLI.md) |
| 🖥️ **Admin Console** | Create, search, and reveal secrets in the browser. Import `.env` files with preview and conflict detection. Export any config as JSON or `.env`. Compare a key across environments to spot drift. | 📖 [Server installation](docs/SERVER_INSTALLATION.md) |
| 🔐 **Tokens, RBAC & audit** | Issue personal and service tokens with TTL and project scoping. Manage workspace roles and groups for least-privilege access. Review every access in a filterable audit trail. | 📖 [First-time setup](docs/FIRST_TIME_SETUP.md) |
| ⚡ **CLI runtime injection** | Run any command through `ssm-cli run` and your secrets arrive as environment variables. Download, upload, and mount secret payloads for local use and CI/CD. | 📖 [CLI guide](docs/CLI.md) |
| 🔄 **Auto-sync to containers** | Label a Docker container once. The `ssm-reload` service recreates it with fresh environment whenever its secrets change. No manual redeploys. Watch every instance and its last outcome from the Admin Console's Reloader Fleet view. | 📖 [Secrets reloader](docs/SECRETS_RELOADER.md) |

Also in the box: automatic secret icons for large catalogs, cross-config drift detection, FIFO secret mounts, and a deprecation-stable API.

## 🚀 Get Started

### 1. Deploy the server

```bash
git clone https://github.com/bearlike/Simple-Secrets-Manager.git
cd Simple-Secrets-Manager
./scripts/deploy_stack.sh
```

Open `http://localhost:8080`, create the first admin user, and add your first secrets.

> 📖 **Full guide:** [Server installation](docs/SERVER_INSTALLATION.md)

### 2. Install the CLI

```bash
uv tool install git+https://github.com/bearlike/Simple-Secrets-Manager.git
ssm-cli configure --base-url http://localhost:8080/api --profile dev
ssm-cli login --profile dev
ssm-cli run --profile dev -- python app.py
```

> 📖 **Full guide:** [CLI installation & reference](docs/CLI.md)

### 3. Keep containers in sync (optional)

```yaml
services:
  web:
    image: myorg/web-api:latest
    labels:
      com.bearlike.ssm.enable: "true"       # opt in
      com.bearlike.ssm.config: "web/prod"   # project/config to track
```

Already running the stack from step 1? `docker compose --profile reload up -d` is the quickest way to bring `ssm-reload` up. Otherwise, run the service next to your workloads; any labeled container is recreated with fresh secrets when they change.

> 📖 **Full guide:** [Secrets reloader](docs/SECRETS_RELOADER.md)

## 📚 Documentation

| Guide | What it covers |
| --- | --- |
| [Server installation](docs/SERVER_INSTALLATION.md) | Deploying the stack, endpoints, updating an existing deployment. |
| [First-time setup](docs/FIRST_TIME_SETUP.md) | Bootstrapping the first admin, tokens, and workspace RBAC. |
| [CLI](docs/CLI.md) | Installing `ssm-cli`, authentication, commands, resolution order. |
| [Secrets reloader](docs/SECRETS_RELOADER.md) | Auto-syncing secrets to running Docker containers. |
| [Container image](docs/README_dockerhub.md) | Image tags, ports, and runtime reference. |
| [Contributing](docs/CONTRIBUTING.md) | Prerequisites, local development, quality gates, and commit conventions. |

## 🤝 Contributing

Fork, branch, and open a pull request — the pre-commit hook runs the same lint/test gate as CI. Start with the [contributing guide](docs/CONTRIBUTING.md).

Found a bug or want a feature? Open an issue on the [issue tracker](https://github.com/bearlike/Simple-Secrets-Manager/issues) with reproduction steps where possible.

---

Licensed under [CC0 1.0 Universal](./LICENSE).
