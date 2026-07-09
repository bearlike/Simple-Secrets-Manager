"""The embedded ``using-ssm`` agent skill and its installer.

The skill teaches coding agents (Claude Code, Codex) how to drive
``ssm-cli`` safely -- discover secrets without leaking values, run
commands with secrets injected, and ask before any mutation. It ships as a
module-level string (not package-data) on purpose: it is one short,
generated file, so embedding it keeps packaging config out of the
contested ``pyproject.toml`` and guarantees it can never be dropped from a
built wheel. Writes go through :func:`ssm_cli.fsio.atomic_write_text` so a
half-written ``SKILL.md`` is never observed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ssm_cli.fsio import atomic_write_text

SKILL_NAME = "using-ssm"

# The agents we can install for, and the config directory each keeps its
# skills under (``~/.claude`` for user scope, ``.claude`` for project scope).
AGENT_DIRS: dict[str, str] = {"claude": ".claude", "codex": ".codex"}

Agent = Literal["claude", "codex"]
Scope = Literal["user", "project"]

# The product itself. Keep it short and rot-proof: point agents at
# ``--help`` for anything not spelled out here. Every physical line stays
# <=79 chars (ruff E501 counts string lines too); the frontmatter
# description is a YAML folded scalar so it reads as one logical line while
# still wrapping in source.
SKILL_MARKDOWN = """---
name: using-ssm
description: >-
  Use Simple Secrets Manager (ssm-cli) to discover a project's secrets and
  inject them as environment variables when running project commands. Use
  when a task needs API keys, tokens, env vars, or ".env" values, or asks
  to run or bootstrap a project that depends on secrets.
---

# Using Simple Secrets Manager (ssm-cli)

Simple Secrets Manager (SSM) keeps a team's secrets on a self-hosted
server. `ssm-cli` fetches them over HTTP and injects them into commands as
environment variables, so a project runs with no `.env` file on disk.

## Concept ladder

`workspace` -> `project` -> `config` -> secret `KEY`s. Configs form a tree:
a child config inherits its parent's keys and may override them. Bind the
current directory to a project/config with `ssm-cli setup` (it writes
`.ssm/config.json`); `--profile` picks which server/identity to use.

## Discover (safe, read-only -- do this first)

- `ssm-cli whoami` -- who am I, which server and workspace.
- `ssm-cli projects list` -- projects you can access.
- `ssm-cli configs list --project <p>` -- configs inside a project.
- `ssm-cli secrets keys` -- KEY NAMES for the bound project/config.

Prefer `secrets keys` to learn what exists. Do NOT print secret VALUES
into logs, transcripts, or the terminal.

## Run with secrets injected

`ssm-cli run [--project P --config C] -- <command>` runs `<command>` with
the resolved secrets as environment variables and exits with the command's
own exit code. Use it to bootstrap or run project commands instead of
exporting values yourself.

## Permission rule (ask first, every time)

Any MUTATION -- changing secrets (`ssm-cli secrets set`, `secrets upload`,
or any delete) and any workspace, user, or token change -- and any command
that would DISPLAY secret values requires EXPLICIT user consent for that
specific action, every time. Never mutate or reveal values on your own
initiative. Read-only discovery and `ssm-cli run` are fine without asking.

## When unsure

For everything else run `ssm-cli --help` or `ssm-cli <group> --help`, and
trust the CLI's own help over this file.
"""


@dataclass(frozen=True)
class SkillInstallResult:
    """One (agent, scope) outcome from an install run.

    ``status`` is ``"installed"`` when the file was written, or
    ``"skipped"`` when a user-scope target was requested for an agent that
    is not present on this machine (``detail`` says why).
    """

    agent: str
    scope: Scope
    path: Path
    status: Literal["installed", "skipped"]
    detail: str = ""


class AgentSkillInstaller:
    """Resolves where the ``using-ssm`` skill goes and writes it there.

    Destinations are injected (``home`` / ``project_root``) rather than read
    from the process so the installer is testable without touching the real
    home directory. Project scope always installs (directories are
    created); user scope installs only where the tool is already present --
    ``~/.claude`` for claude, ``~/.codex`` for codex -- and otherwise skips
    with a clear message instead of erroring. Each run overwrites the file:
    it is generated, so there is no ``--force`` to reason about.
    """

    def __init__(
        self,
        content: str = SKILL_MARKDOWN,
        *,
        home: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._content = content
        self._home = home if home is not None else Path.home()
        self._project_root = (
            project_root if project_root is not None else Path.cwd()
        )

    def _skill_path(self, base: Path, agent: str) -> Path:
        return base / AGENT_DIRS[agent] / "skills" / SKILL_NAME / "SKILL.md"

    def user_detected(self, agent: str) -> bool:
        """True when ``agent``'s user config dir exists (so a user install
        is wanted). Mirrors Grove's "install for user only if they exist"
        rule."""
        return (self._home / AGENT_DIRS[agent]).exists()

    def install(
        self, agents: list[str], scopes: list[Scope]
    ) -> list[SkillInstallResult]:
        results: list[SkillInstallResult] = []
        for agent in agents:
            for scope in scopes:
                results.append(self._install_one(agent, scope))
        return results

    def _install_one(self, agent: str, scope: Scope) -> SkillInstallResult:
        if scope == "user":
            path = self._skill_path(self._home, agent)
            if not self.user_detected(agent):
                return SkillInstallResult(
                    agent=agent,
                    scope=scope,
                    path=path,
                    status="skipped",
                    detail=(
                        f"{agent} not detected (~/{AGENT_DIRS[agent]} missing)"
                    ),
                )
        else:
            path = self._skill_path(self._project_root, agent)

        atomic_write_text(path, self._content, mode=0o644)
        return SkillInstallResult(
            agent=agent, scope=scope, path=path, status="installed"
        )
