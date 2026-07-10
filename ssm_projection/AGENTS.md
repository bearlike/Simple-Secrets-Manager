# ssm_projection — Agent Guide

> Nearest-scope guide for `ssm_projection/`. Read the [root `AGENTS.md`](../AGENTS.md)
> first for cross-cutting principles and the memory protocol. This file
> captures only what is **not obvious from the code** in this scope.
> `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

Render a `project/config`'s secrets to a dotenv file in a pluggable sink — the
**delivery** half of SSM, as opposed to the reloader's convergence half.

| Module | Answers |
| --- | --- |
| `dotenv.py` | How is a secret map rendered so a dotenv parser reads it back byte-for-byte (`render_dotenv`), and which key names are rejected? |
| `sink.py` | Where does a rendered config land — the `ProjectionSink` seam, the `DirectorySink` implementation, the `<project>-<config>.env` name, and the `0640` mode. |
| `fsio.py` | `atomic_write_text` — the write-temp-fsync-chmod-rename dance every concurrent writer needs. |
| `__init__.py` | The public surface (re-export list). Import from here, not from the modules. |

## Non-obvious decisions

- **This is a LEAF, and it exists because TWO deployables must render the same
  bytes.** `ssm_cli` (`ssm secrets materialize`) and `ssm_reload` (the
  projection loop) both write the same `env_file`, and `docker compose` folds
  an `env_file`'s **contents** into its config hash. Two renderers that
  disagreed on so much as key order would make every `compose up` recreate
  services the reloader had just settled, and vice versa — an infinite
  recreate war between two tools that each think they are right. One renderer,
  imported by both, is the fix. It imports no app package (import-linter
  enforces the leaf rule), so the reloader's hard isolation from the backend
  still holds.
- **Every value is double-quoted, with `\`, `"`, `$`, `\n` and `\r` escaped.
  The `$` is the load-bearing one.** Compose parses an `env_file` with a
  dotenv parser that **expands `$VAR` in an unquoted value**: a password
  containing `$` would be silently replaced by whatever the compose *client*
  has in its own environment (usually nothing), and the workload would come up
  with a corrupted secret and no error anywhere. Verified live against Compose
  v5.3.1 / Docker 29.6.1: with this escaping, values holding spaces, `#`, `=`,
  quotes, tabs, leading/trailing padding and multi-line PEM bodies all
  round-trip byte-for-byte into the container's environment. `\n`/`\r` are
  unescaped *back* into real newlines by compose, so a multi-line secret (a PEM
  key) survives — which plain env injection could never do.
- **Keys are sorted, and the output is a pure function of the map.** Same
  reason: a reshuffled render is a different config hash, which is a spurious
  recreate of every consuming service.
- **An invalid key name RAISES.** `ENV_KEY_PATTERN` is the POSIX shape
  (`^[A-Za-z_][A-Za-z0-9_]*$`). Docker itself is laxer, but a dotenv parser is
  not — a key outside it produces a file compose cannot read, which fails the
  whole stack rather than one variable. Callers catch this and refuse to write
  (the reloader logs it and leaves the previous, valid file in place).
- **`atomic_write_text` moved here from `ssm_cli/fsio.py`** (which is now a
  documented re-export, so the CLI keeps its own named seam). The reloader
  needs the identical dance: a compose client can read a projected file at any
  moment, and a half-written file parses as a *truncated set of secrets* — not
  as an error. See the concurrency-crash lesson in
  [`../ssm_cli/AGENTS.md`](../ssm_cli/AGENTS.md) for why the temp file must be
  unique per writer.

## Session Lessons (Non-Trivial)

- **`render_dotenv`'s output is for a DOTENV PARSER, and `docker run --env-file`
  is not one — the two env formats are NOT interchangeable.** Docker's
  `--env-file` does a naive `KEY=VALUE` split and takes the value *literally*,
  quotes included; `docker compose`'s `env_file:` runs a real dotenv parser that
  strips them. So a projected file (`ssm secrets materialize`, quoted by
  design — see the `$` decision above) fed to `docker run --env-file` injects
  `MY_KEY="value"` **with the quotes baked into the value**, and the app reads a
  corrupted secret with no error anywhere. Verified live (Docker 29.6.1):
  compose yields `10.2.0.1`, `docker run --env-file` yields `"10.2.0.1"` from the
  identical file. The unquoted `ssm secrets download --format env`
  (`ssm_cli/run_utils.py::render_env_lines`) IS docker's dialect — that is the
  one to pair with `--env-file`, ideally via process substitution
  (`--env-file <(ssm secrets download ... --format env)`) so plaintext never
  reaches disk. Do not "unify" the two renderers to kill the apparent
  duplication: they serve two different parsers, and collapsing them silently
  breaks one consumer or the other. The console's copy-paste snippets encode
  this split (`frontend/src/lib/snippets.ts`).
- **`DirectorySink` deliberately covers BOTH sinks in the design.** The default
  target is an SSM-owned tmpfs Docker volume and the alternate is a host path
  (for systemd's `EnvironmentFile=` and a host-side `docker compose`, which
  cannot read a named volume — its backing path lives inside the daemon's
  storage). Those differ only in *what is mounted at the directory*, not in
  code, so a second sink class would have been pure ceremony. `ProjectionSink`
  is the seam that earns its keep when a genuinely different target arrives (a
  Kubernetes Secret) — don't add sink classes that only differ by mount.
