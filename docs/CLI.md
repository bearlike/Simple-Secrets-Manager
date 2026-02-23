# CLI Reference

Simple Secrets Manager ships with a Doppler-like CLI implemented with Click + Rich.

## Install and run with UVX (recommended)

Run from anywhere without cloning this repository:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm --help
```

Pin to a release tag:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git@v1.3.0 ssm --help
```

Pin to a commit SHA:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git@<commit-sha> ssm --help
```

Local development fallback (inside this repo):

```bash
uv run ssm --help
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

Test overrides via env vars:

- `SSM_GLOBAL_CONFIG_FILE`
- `SSM_LOCAL_CONFIG_FILE`
- `SSM_CREDENTIALS_FILE`
- `SSM_CACHE_DIR`

## Authentication

### Login (username/password)

Uses legacy `GET /api/auth/tokens/` with HTTP Basic auth and stores returned token.

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm configure --base-url http://localhost:8080/api --profile dev
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm login --profile dev
```

### Service/personal token (recommended for CI or automation)

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm auth set-token --profile dev --token "<token>"
```

### Logout

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm logout --profile dev
```

Clear all local token records:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm logout --all-profiles
```

## Project/config setup

Set local defaults for current directory:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm setup --project my-project --config dev --profile dev
```

## Core commands

### Run command with injected secrets

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm run --profile dev -- python app.py
```

Useful flags:

- `--offline`: cache-only
- `--cache-ttl <seconds>`: cache freshness window
- `--print-env`: print resolved keys
- `--show-values`: print values (only with `--print-env`)

### Download secrets

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm secrets download --profile dev --format json
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm secrets download --profile dev --format env
```

Note: `.env` output fails when any value contains a newline. Use JSON in that case.

### Mount secrets to FIFO

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm secrets mount --profile dev --path /tmp/ssm-secrets.fifo --format json
```

- Creates FIFO with `0600` permissions.
- Writes one payload then removes FIFO unless `--keep` is used.

### Session validation

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm whoami --profile dev
```

`whoami` validates token by calling `GET /projects` and reports visible scope behavior.

## Profiles

List profiles:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm profile list
```

Activate profile:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm profile use dev
```

Set profile defaults:

```bash
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git ssm profile set dev --base-url http://localhost:8080/api --project my-project --config dev --activate
```

## Exit behavior

- `run` exits with the child process exit code.
- Configuration/auth errors generally use exit code `2`.
- Offline cache miss uses exit code `4`.

## Local quality checks (for maintainers)

```bash
./scripts/quality.sh check
cd frontend && npm run lint && npm run build
```
