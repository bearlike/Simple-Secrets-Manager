# ssm-cli

The command-line client for Simple Secrets Manager. It authenticates to
your SSM server and **injects your project/config secrets into any
command** — no `.env` files on disk, no copy-pasting values. Drive your
project with a coding agent? `ssm-cli skills install` teaches Claude Code
or Codex to use it safely.

## Install

```bash
uv tool install git+https://github.com/bearlike/Simple-Secrets-Manager.git
uv tool update-shell
ssm-cli --help
```

## Quick start

```bash
# Point at your server and sign in
ssm-cli configure --base-url http://localhost:8080/api --profile dev
ssm-cli login --profile dev

# Bind this directory to a project/config
ssm-cli setup --project my-project --config dev --profile dev

# Run anything with secrets injected as environment variables
ssm-cli run --profile dev -- python app.py
```

`ssm-cli run` resolves secret references (`${KEY}`, `${config.KEY}`,
`${project.config.KEY}`) by default and exits with your command's exit
code, so it drops cleanly into scripts and CI.

## Beyond `run`

- `projects list` / `configs list` / `secrets keys` — read-only discovery
  (`secrets keys` prints key names only, never values)
- `secrets download` — export a config as JSON or `.env` (to stdout)
- `secrets set` / `secrets upload` — write one secret or bulk-import
  from `.env`/JSON
- `secrets mount` — deliver secrets through a FIFO instead of env
- `skills install` — install the `using-ssm` agent skill for Claude Code
  or Codex (project or user scope)
- `workspace ...` — manage members, groups, and project roles
- `profile ...` — switch between servers and environments

## Documentation

Full reference — every command, resolution order, file locations, and
exit codes: [`docs/CLI.md`](../docs/CLI.md)
