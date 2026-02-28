from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ssm_cli import auth
from ssm_cli.api import normalize_base_url
from ssm_cli.config import (
    DEFAULT_PROFILE,
    load_global_config,
    load_local_config,
)
from ssm_cli.exceptions import CliError


@dataclass
class Resolution:
    profile: str
    base_url: str | None
    project: str | None
    config: str | None
    token: str | None
    token_source: str | None


def _pick(*values: str | None) -> str | None:
    for value in values:
        if value is not None:
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def resolve_context(
    *,
    base_url: str | None = None,
    project: str | None = None,
    config: str | None = None,
    profile: str | None = None,
    cwd: Path | None = None,
    require_base_url: bool = False,
    require_project_config: bool = False,
    require_token: bool = False,
) -> Resolution:
    global_cfg = load_global_config()
    local_cfg = load_local_config(cwd)

    resolved_profile = _pick(
        profile,
        os.getenv("SSM_PROFILE"),
        local_cfg.profile,
        global_cfg.active_profile,
        DEFAULT_PROFILE,
    )
    if resolved_profile is None:
        resolved_profile = DEFAULT_PROFILE

    profile_cfg = global_cfg.profiles.get(resolved_profile)

    resolved_base_url = _pick(
        base_url,
        os.getenv("SSM_BASE_URL"),
        profile_cfg.base_url if profile_cfg else None,
        global_cfg.base_url,
    )
    if resolved_base_url:
        resolved_base_url = normalize_base_url(resolved_base_url)

    resolved_project = _pick(
        project,
        os.getenv("SSM_PROJECT"),
        local_cfg.project,
        profile_cfg.project if profile_cfg else None,
    )
    resolved_config = _pick(
        config,
        os.getenv("SSM_CONFIG"),
        local_cfg.config,
        profile_cfg.config if profile_cfg else None,
    )

    env_token = _pick(os.getenv("SSM_TOKEN"))
    if env_token is not None:
        token = env_token
        token_source = "env"
    else:
        token = None
        token_source = None
        if resolved_base_url:
            token, token_source = auth.get_token(
                resolved_profile, resolved_base_url
            )

    result = Resolution(
        profile=resolved_profile,
        base_url=resolved_base_url,
        project=resolved_project,
        config=resolved_config,
        token=token,
        token_source=token_source,
    )

    if require_base_url and not result.base_url:
        raise CliError(
            "Base URL is not configured. Run `ssm configure` or pass "
            "--base-url.",
            exit_code=2,
        )

    if require_project_config and (not result.project or not result.config):
        raise CliError(
            "Project/config is not configured. Run `ssm setup` or pass "
            "--project and --config.",
            exit_code=2,
        )

    if require_token and not result.token:
        raise CliError(
            "Token is not configured. Run `ssm login` or "
            "`ssm auth set-token`.",
            exit_code=2,
        )

    return result
