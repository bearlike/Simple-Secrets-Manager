# CLI Reference

Simple Secrets Manager ships with a Doppler-like CLI implemented with Click + Rich.

## Install and verify

From repository root:

```bash
uv sync
uv run ssm --help
```

If you prefer direct binary execution after sync:

```bash
.venv/bin/ssm --help
```

## Resolution order (DRY/KISS)

The CLI resolves values using one deterministic order.

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

## Config and credential files

- Global config: `~/.config/ssm/config.json`
- Local config: `<current-dir>/.ssm/config.json`
- Credential fallback: `~/.config/ssm/credentials.json` (mode `0600`)
- Cache: `~/.cache/ssm/secrets/<hash>.json`

Test overrides are supported via env vars:

- `SSM_GLOBAL_CONFIG_FILE`
- `SSM_LOCAL_CONFIG_FILE`
- `SSM_CREDENTIALS_FILE`
- `SSM_CACHE_DIR`

## Authentication

### Login (username/password)

Uses legacy `GET /api/auth/tokens/` with HTTP Basic auth and stores returned token.

```bash
uv run ssm configure --base-url http://localhost:8080/api --profile dev
uv run ssm login --profile dev
```

### Service/personal token (recommended for CI or automation)

```bash
uv run ssm auth set-token --profile dev --token "<token>"
```

### Logout

```bash
uv run ssm logout --profile dev
```

Clear all local token records:

```bash
uv run ssm logout --all-profiles
```

## Project/config setup

Set local defaults for current directory:

```bash
uv run ssm setup --project my-project --config dev --profile dev
```

## Core commands

### Run command with injected secrets

```bash
uv run ssm run --profile dev -- python app.py
```

Useful flags:

- `--offline`: cache-only
- `--cache-ttl <seconds>`: cache freshness window
- `--print-env`: print resolved keys
- `--show-values`: print values (only with `--print-env`)

### Download secrets

```bash
uv run ssm secrets download --profile dev --format json
uv run ssm secrets download --profile dev --format env
```

Note: `.env` output fails when any value contains a newline. Use JSON in that case.

### Mount secrets to FIFO

```bash
uv run ssm secrets mount --profile dev --path /tmp/ssm-secrets.fifo --format json
```

- Creates FIFO with `0600` permissions.
- Writes one payload then removes FIFO unless `--keep` is used.

### Session validation

```bash
uv run ssm whoami --profile dev
```

`whoami` validates token by calling `GET /projects` and reports visible scope behavior.

## Profiles

List profiles:

```bash
uv run ssm profile list
```

Activate profile:

```bash
uv run ssm profile use dev
```

Set profile defaults:

```bash
uv run ssm profile set dev --base-url http://localhost:8080/api --project my-project --config dev --activate
```

## Exit behavior

- `run` exits with the child process exit code.
- Configuration/auth errors generally use exit code `2`.
- Offline cache miss uses exit code `4`.

## Local quality checks

```bash
./scripts/quality.sh check
cd frontend && npm run lint && npm run build
```
