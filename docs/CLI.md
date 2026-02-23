# CLI Reference

`ssm-cli` is the command-line client for Simple Secrets Manager.

## 1) Install Once (Recommended)

Install globally with uv tools:

```bash
uv tool install git+https://github.com/bearlike/Simple-Secrets-Manager.git
uv tool update-shell
ssm-cli --help
```

If command is not found in a new shell:

```bash
export PATH="$(uv tool dir --bin):$PATH"
```

Upgrade later:

```bash
uv tool upgrade simple-secrets-manager
```

Uninstall:

```bash
uv tool uninstall simple-secrets-manager
```

## 2) Ephemeral Run (No Install)

Use UVX directly when you do not want a persistent install:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm-cli --help
```

Pin to tag:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git@v1.3.0 ssm-cli --help
```

## 3) Quick Start

Configure backend URL:

```bash
ssm-cli configure --base-url http://localhost:8080/api --profile dev
```

Authenticate:

```bash
ssm-cli login --profile dev
# or
ssm-cli auth set-token --profile dev --token "<token>"
```

Set default project/config for current directory:

```bash
ssm-cli setup --project my-project --config dev --profile dev
```

Run your app with injected secrets:

```bash
ssm-cli run --profile dev -- python app.py
```

## Core Commands

Download secrets:

```bash
ssm-cli secrets download --profile dev --format json
ssm-cli secrets download --profile dev --format env
```

Mount secrets to FIFO:

```bash
ssm-cli secrets mount --profile dev --path /tmp/ssm-secrets.fifo --format json
```

Validate current session:

```bash
ssm-cli whoami --profile dev
```

Profile management:

```bash
ssm-cli profile list
ssm-cli profile use dev
ssm-cli profile set dev --base-url http://localhost:8080/api --project my-project --config dev --activate
```

## Resolution Order

### Base URL

1. `--base-url`
2. `SSM_BASE_URL`
3. active profile in global config
4. global `base_url`

### Project and config

1. `--project` / `--config`
2. `SSM_PROJECT` / `SSM_CONFIG`
3. local directory config (`.ssm/config.json`)
4. active profile defaults in global config

### Profile

1. `--profile`
2. `SSM_PROFILE`
3. local directory profile (`.ssm/config.json`)
4. global active profile
5. `default`

### Token

1. `SSM_TOKEN`
2. stored token for `<profile>@<base_url>` in keyring
3. stored token in file fallback

## File Locations

- Global config: `~/.config/ssm/config.json`
- Local config: `<current-dir>/.ssm/config.json`
- Credential fallback: `~/.config/ssm/credentials.json` (`0600`)
- Cache: `~/.cache/ssm/secrets/<hash>.json`

Test overrides via env vars:

- `SSM_GLOBAL_CONFIG_FILE`
- `SSM_LOCAL_CONFIG_FILE`
- `SSM_CREDENTIALS_FILE`
- `SSM_CACHE_DIR`

## Exit Behavior

- `run` exits with child process exit code.
- Configuration/auth errors typically exit `2`.
- Offline cache miss exits `4`.

## Maintainer Checks

```bash
./scripts/quality.sh check
cd frontend && npm run lint && npm run build
```
