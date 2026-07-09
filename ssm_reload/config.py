"""Environment-driven configuration.

All configuration comes from the environment (12-factor). The read-only,
scoped SSM token is env-only and never logged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from ssm_reload.errors import SsmReloadError

DEFAULT_POLL_INTERVAL = 30.0
DEFAULT_LABEL_PREFIX = "ssm"


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration."""

    base_url: str
    token: str
    poll_interval: float = DEFAULT_POLL_INTERVAL
    label_prefix: str = DEFAULT_LABEL_PREFIX
    docker_host: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        """Build a :class:`Config` from environment variables.

        Raises :class:`SsmReloadError` when a required variable is
        missing so the service fails fast on start-up rather than
        looping uselessly.
        """
        source = os.environ if env is None else env

        base_url = (source.get("SSM_BASE_URL") or "").strip()
        if not base_url:
            raise SsmReloadError("SSM_BASE_URL is required")

        token = (source.get("SSM_TOKEN") or "").strip()
        if not token:
            raise SsmReloadError("SSM_TOKEN is required")

        prefix = (
            source.get("SSM_RELOAD_LABEL_PREFIX") or DEFAULT_LABEL_PREFIX
        ).strip() or DEFAULT_LABEL_PREFIX

        docker_host = source.get("DOCKER_HOST") or None

        return cls(
            base_url=base_url,
            token=token,
            poll_interval=_parse_interval(
                source.get("SSM_RELOAD_POLL_INTERVAL")
            ),
            label_prefix=prefix,
            docker_host=docker_host,
        )


def _parse_interval(value: str | None) -> float:
    if value is None or not value.strip():
        return DEFAULT_POLL_INTERVAL
    try:
        interval = float(value)
    except ValueError:
        return DEFAULT_POLL_INTERVAL
    return interval if interval > 0 else DEFAULT_POLL_INTERVAL
