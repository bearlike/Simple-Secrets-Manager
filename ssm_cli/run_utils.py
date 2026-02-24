from __future__ import annotations

import os
import subprocess
from typing import Iterable

from ssm_cli.exceptions import CliError


def merge_env(secrets: dict[str, str], base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env if base_env is not None else os.environ)
    env.update(secrets)
    return env


def render_env_lines(secrets: dict[str, str]) -> str:
    lines = []
    for key, value in secrets.items():
        if "\n" in value:
            raise CliError(f"Value for {key} contains newline; env format does not support it", exit_code=3)
        lines.append(f"{key}={value}")
    return "\n".join(lines)


def run_with_env(command: Iterable[str], secrets: dict[str, str]) -> int:
    merged_env = merge_env(secrets)
    completed = subprocess.run(list(command), env=merged_env, check=False)
    return completed.returncode
