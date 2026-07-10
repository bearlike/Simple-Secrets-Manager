# ssm_cli — Agent Guide

> Nearest-scope guide for `ssm_cli/`. Read the [root `AGENTS.md`](../AGENTS.md)
> first for cross-cutting principles and the memory protocol. This file
> captures only what is **not obvious from the code** in this scope.
> `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

The `ssm` / `ssm-cli` client — authenticates and injects project/config
secrets into commands (`ssm run -- ...`), talking to the API over HTTP.

| Module | Answers |
| --- | --- |
| `main.py` | What commands exist (`configure`, `login`/`logout`, `run`, `secrets download/set/upload/mount/materialize/keys`, `projects list`, `configs list`, `workspace ...`, `profile ...`, `skills install`), and where does every exception get turned into a clean `Error: ...` line? |
| `api.py` | How is a request built/retried against the REST API, and how is an error message pulled out of a failed response? |
| `auth.py` | Where does a token get stored and read back — OS keyring or the file-backed credentials store? |
| `cache.py` | Where do last-fetched secrets get cached for `--offline`/fallback use, and when is that cache considered stale or invalid? |
| `config.py` | Where do the global (`~/.config/ssm/config.json`), local (`.ssm/config.json`), and credentials (`~/.config/ssm/credentials.json`) files live, and what are their env-var path overrides? |
| `fsio.py` | How is a JSON file written so concurrent `ssm` processes can't corrupt it? (A re-export: the implementation lives in the `ssm_projection` leaf, which the reloader needs too.) |
| `resolve.py` | What's the precedence order (flag > env var > local config > profile config) when the same setting is set in more than one place? |
| `run_utils.py` | How do resolved secrets get merged into a child process's environment for `ssm run -- ...`, and how is its exit code propagated back? |
| `agent_skill.py` | What does `skills install` write, and for which coding agents/scopes (the embedded `using-ssm` skill for Claude Code/Codex, user or project scope)? |
| `exceptions.py` | What's `CliError`, and how does its `exit_code` reach the shell? |
| `__main__.py` | Entry point for `python -m ssm_cli`. |

## Non-obvious decisions

- **All local JSON state funnels through `fsio.py::atomic_write_text`.**
  `cache.py::save_secret_cache` and every `config.py` writer
  (`save_global_config`, `save_local_config`, `save_credentials`, via
  `_atomic_write_json`) call it — there is no other write path. WHY: many
  `ssm` processes can touch the same cache/config/credentials files at
  once (e.g. parallel `ssm run` invocations); the helper gives each writer
  its own `tempfile.mkstemp(dir=target_dir)` temp file, `fsync`s before
  `os.replace`, and unlinks its own temp file on any failure. A hand-rolled
  `path + ".tmp"` style write would let two writers collide on the same
  temp name (see Session Lessons). `fsio.py` is now a one-line re-export of
  `ssm_projection.atomic_write_text` — the CLI keeps its own named seam, but
  there is exactly ONE implementation, because `ssm-reload` needs the same
  dance for projected `.env` files.
- **`secrets materialize` and `ssm-reload` must render byte-identical files,
  which is why both call `ssm_projection.render_dotenv`.** `docker compose`
  folds an `env_file`'s CONTENTS into its config hash: if the CLI wrote a file
  that differed from the reloader's by so much as key order, every
  `compose up` would recreate services the reloader had just settled, forever.
  Never render a dotenv here by hand (and note `run_utils.render_env_lines` is
  a DIFFERENT thing — an unquoted display/`--format env` rendering for humans
  and shells, not a file a dotenv parser will read back).
- **Readers of local state treat corruption as absence, not an error.**
  `cache.py::load_secret_cache` catches `(OSError, ValueError)` and returns
  `None` (a cache miss, so the caller re-fetches); `config.py::_read_json`
  catches the same pair and returns `{}` (unset, falling back to
  defaults). WHY: a truncated or hand-edited JSON file must degrade
  gracefully — these are best-effort local caches/config, not the source
  of truth.
- **`_handle_errors` in `main.py` is the single seam between internal
  exceptions and user-facing text, and its catch order matters.**
  `CliError`/`ApiError` come first (already carry a message + exit code),
  then `click.exceptions.Exit`/`Abort` are re-raised untouched, then
  `OSError`, then a bare `Exception` catch-all. WHY: the `Exit`/`Abort`
  branch has to sit before the catch-all or it would intercept deliberate
  control flow — specifically `run`'s `raise click.exceptions.Exit(code)`,
  which propagates the child process's real exit code back to the shell.
- **`keyring` is an optional import with per-call failure isolation, not a
  hard dependency.** `auth.py` imports it inside a top-level
  `try/except Exception` (so the module still loads without a keyring
  backend or a working D-Bus), then wraps every individual
  `set_password`/`get_password`/`delete_password` call in its own
  `try/except Exception: pass`, falling through to the file-backed
  `credentials.json` store. `KEYRING_SENTINEL = "__KEYRING__"` is what
  gets written to `credentials.json` when the real token lives in the
  keyring instead — it lets `get_token`'s file-fallback branch tell "no
  token here, it's in the keyring" apart from an actual stored token,
  instead of ever handing back the literal sentinel string as a bearer
  token.
- **API error messages are read `message`-first, matching the API's error
  envelope.** `api.py::_error_message` checks
  `("message", "error", "status")` in that order on a JSON body (or uses
  the raw text for a non-JSON body). WHY: this mirrors the API's
  `{"message": ...}` envelope (see
  [`../ssm_server/api/AGENTS.md`](../ssm_server/api/AGENTS.md));
  `error`/`status` are fallbacks for responses that never came from this
  API (proxies, gateways), not an alternate contract to keep in sync.
- **`SSM_TOKEN` short-circuits credential resolution entirely.** In
  `resolve.py::resolve_context`, if the env var is set it's used as the
  token directly and `auth.get_token` (keyring/file lookup) is never
  called. WHY: lets CI/automation inject a token without touching local
  keyring/file storage at all — but it also means a stale `SSM_TOKEN` in
  the environment silently overrides a fresh `ssm login`, which is a
  common "why isn't my new token being used" trap.
- **The CLI is deliberately NOT migrated to `pydantic-settings` (the
  per-service settings convention the server and reloader follow).**
  `resolve.py`'s flag > env > local-config > profile precedence engine IS
  this client's single config source of truth; a `pydantic-settings` model
  would both duplicate that layered precedence and drag a heavy dependency
  into the lean CLI-only base install (`uv tool install` must stay light —
  see the extras layout in `pyproject.toml`). Keep configuration flowing
  through `resolve.py`, not a settings class. The single DRY rule the CLI
  DOES follow: **`SSM_PROFILE` is read in exactly one place** —
  `resolve.py::profile_from_env()` — which both `resolve_context` and
  `main._profile_name` call, so the variable can't be read two subtly
  different ways.

## Session Lessons (Non-Trivial)

- **Concurrency crash (fixed in `fsio.py`):** before this module existed,
  local JSON writes derived their temp filename from the target path.
  Under concurrent `ssm` invocations two writers landed on the same temp
  file; the loser's `os.chmod`/`os.replace` then crashed with
  `FileNotFoundError` once the winner had already renamed it away. The
  fix was to centralize every write behind `atomic_write_text`, which
  mints a unique temp file per call via `tempfile.mkstemp(dir=parent)`.
  Never hand-roll temp-then-rename for a new local JSON write — route it
  through this helper.
- **Error-handling ordering is deliberate, not incidental:** the
  last-resort `except Exception` in `_handle_errors` was added together
  with the explicit `except (click.exceptions.Exit, click.exceptions.Abort):
  raise` placed before it. Adding a catch-all without that guard would
  silently swallow `run`'s deliberate child-exit-code propagation into a
  generic "Unexpected error" with exit code 1 — breaking any script that
  checks `$?`. Any new deliberately-raised Click control-flow exception
  must be added to that re-raise branch, not just left to the catch-all.
- **`api.py` response-shape validation funnels through two
  helpers — new `ApiClient` methods must use them, not hand-roll the
  check.** `ApiClient._expect_dict(payload, what)` and
  `ApiClient._expect_list(payload, key, what)` are the single seam for the
  two verbatim shapes that used to be copy-pasted across ~20 methods: "is
  the parsed body a dict, else raise `ApiError(f'{what} response is
  invalid', ...)`" and "is `payload[key]` a list of dicts, else raise (same
  message shape), else filter to dict items". `login_userpass` (needs an
  extra `payload.get("token")` str check) and
  `list_workspace_group_members` (its list holds `str` items, not `dict`)
  are deliberately NOT routed through these helpers — they're one-off
  shapes, not the shared pattern; don't force them through `_expect_*` just
  for uniformity. Add any new dict/list-of-dicts response method through
  `_expect_dict`/`_expect_list` with a short `what` noun instead of
  re-writing the `isinstance` check.
- **`main.py`'s `--profile`/`--base-url` Click options are
  reusable decorator objects, not a stacked `common_options`.**
  `profile_option = click.option("--profile", default=None, help="Profile
  name")` and `base_url_option = click.option("--base-url", default=None,
  help="Base URL override")` (defined once, just above the `cli` group) are
  safe to apply to many commands: Click's `option()` returns a decorator
  closure that copies its `attrs` dict and builds a fresh `Option` instance
  on every application, so reusing the same decorator object across ~30
  commands doesn't share mutable state between them — this is Click's own
  documented reusable-option idiom, not a hack. A single stacked
  `common_options` bundling `--base-url`+`--project`+`--config`+`--profile`
  together was considered and rejected: several commands (e.g. `run`) have
  `--project`/`--config` options interspersed between the two, so bundling
  would force reordering call sites for no behavior change. `configure`'s
  `--base-url` (required, distinct help text) and `profile set`'s
  `--base-url` (sets a profile field, not a request override — help is
  plain "Base URL", no "override") are deliberately excluded from
  `base_url_option`: different semantics, not drift.
