# CLI Reference

`ssm-cli` is the command-line client for Simple Secrets Manager.

> [!TIP]
> Using a coding agent (Claude Code, Codex)? Run `ssm-cli skills install` to
> teach it how to use `ssm-cli` safely — discover secrets without leaking
> values, run commands with secrets injected, and ask before any mutation.
> One command, project or user scope. See
> [Skills for coding agents](#skills-for-coding-agents).

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

If installed from Git and you want a fresh reinstall:

```bash
uv tool install --force git+https://github.com/bearlike/Simple-Secrets-Manager.git
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
uvx --from git+https://github.com/bearlike/Simple-Secrets-Manager.git@v1.5.0 ssm-cli --help
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

`ssm-cli run` resolves secret references by default (`${KEY}`, `${config.KEY}`, `${project.config.KEY}`) through the backend API.

Verify injection against an existing config by printing one expected key from the child environment:

```bash
ssm-cli run --profile dev -- printenv EXAMPLE_API_KEY
```

## Core Commands

Download secrets:

```bash
ssm-cli secrets download --profile dev --format json
ssm-cli secrets download --profile dev --format env
ssm-cli secrets download --profile dev --format json --raw
```

Set one secret:

```bash
ssm-cli secrets set --profile dev --key API_KEY --value "super-secret"
printf '%s' "$TOKEN_VALUE" | ssm-cli secrets set --profile dev --key TOKEN --value-stdin
```

Upload many secrets:

```bash
ssm-cli secrets upload --profile dev --env-file .env.production
ssm-cli secrets upload --profile dev --json-file ./secrets.json
cat ./secrets.json | ssm-cli secrets upload --profile dev --stdin --format json
```

Mount secrets to FIFO:

```bash
ssm-cli secrets mount --profile dev --path /tmp/ssm-secrets.fifo --format json
ssm-cli secrets mount --profile dev --path /tmp/ssm-secrets.fifo --format env --raw
```

Validate current session:

```bash
ssm-cli whoami --profile dev
```

Discover projects, configs, and secret keys (read-only, safe for agents):

```bash
ssm-cli projects list --profile dev
ssm-cli configs list --project my-project --profile dev
ssm-cli secrets keys --profile dev
```

`projects list` and `configs list` resolve the base URL/token (and, for
configs, the project) through the usual resolution order. `secrets keys`
prints KEY NAMES only — never values — so an agent can learn what a config
contains without a secret ever landing in a log or transcript.

Workspace and RBAC operations:

```bash
ssm-cli workspace settings --profile dev
ssm-cli workspace members --profile dev
ssm-cli workspace member-add --username alice --password 'StrongPass123' --workspace-role viewer --profile dev
ssm-cli workspace groups --profile dev
ssm-cli workspace project-members --project scraper-handler --profile dev
```

Profile management:

```bash
ssm-cli profile list
ssm-cli profile use dev
ssm-cli profile set dev --base-url http://localhost:8080/api --project my-project --config dev --activate
```

## Skills for coding agents

If you drive a project with a coding agent (Claude Code, Codex),
`ssm-cli skills install` writes a short `using-ssm` skill that teaches the
agent to discover secrets safely, run commands with secrets injected, and ask
for consent before any mutation or before revealing a secret value.

```bash
# Choose scope interactively (prompts per scope on a TTY)
ssm-cli skills install

# Or be explicit
ssm-cli skills install --target project          # ./.claude, ./.codex
ssm-cli skills install --target user             # ~/.claude, ~/.codex
ssm-cli skills install --target all --agent claude
```

Flags:

- `--agent claude|codex|all` (default `all`) — which agent(s) to target.
- `--target user|project|all` — install scope. Omit it on an interactive
  terminal to answer a short y/n prompt per scope; on a non-interactive shell
  you must pass `--target` or the command exits `2` with a usage hint.

Destinations (the written file is `.../skills/using-ssm/SKILL.md`):

| Agent | Project scope | User scope |
| --- | --- | --- |
| `claude` | `./.claude/skills/using-ssm/` | `~/.claude/skills/using-ssm/` |
| `codex` | `./.codex/skills/using-ssm/` | `~/.codex/skills/using-ssm/` |

User-scope installs land only where the tool is detected (`~/.claude` exists
for claude, `~/.codex` for codex); an undetected tool is skipped with a
message, not an error. Project scope always installs and creates directories.
The skill file is generated and overwritten on every run.

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

## Workspace Commands (v1.5.0)

`ssm-cli workspace ...` covers user/group/RBAC management:

- Settings:
  - `workspace settings`
  - `workspace settings-set --default-workspace-role ... --default-project-role ... --referencing-enabled true|false`
- Members:
  - `workspace members`
  - `workspace member-add`
  - `workspace member-update`
  - `workspace member-disable`
- Groups:
  - `workspace groups`
  - `workspace group-add|group-update|group-delete`
  - `workspace group-members|group-members-set`
- Group mappings:
  - `workspace mappings`
  - `workspace mapping-add`
  - `workspace mapping-delete`
- Project role assignments:
  - `workspace project-members --project <slug>`
  - `workspace project-member-set --project <slug> --subject-type user|group --subject-id <username|group-slug> --role admin|collaborator|viewer|none`
  - `workspace project-member-remove ...`

Role behavior:

- `owner`: full workspace and project management.
- `admin`: manage projects/tokens/groups/project-memberships; cannot change workspace settings or create/modify workspace users.
- `collaborator` and `viewer`: can list workspace members; project access comes from direct/group project role assignments.

## Exit Behavior

- `run` exits with child process exit code.
- Configuration/auth errors typically exit `2`.
- Offline cache miss exits `4`.
- `secrets upload` exits `1` when any key fails to write.

## Maintainer Checks

```bash
./scripts/quality.sh check
cd frontend && npm run lint && npm run build
```
