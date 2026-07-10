"""The one place ssm-reload reads its environment.

`ReloadSettings` is the single, validated source of configuration for the
reloader: every environment variable the service honors is a declared,
validated field here, and a raw `os.environ` read anywhere else in
`ssm_reload/` is a defect. A scattered config surface once let an unwanted
knob ship unnoticed — one class you can read top to bottom is the fix.

Design (two layers only: model defaults, then environment):

* Fields carry an explicit `validation_alias` matching the EXACT env var name
  operators already set — the operator contract does not change.
* `SSM_TOKEN` is a `SecretStr`, so no repr or log can leak it; unwrap with
  `.get_secret_value()` only at the single point of use (building the
  `SsmClient` in `runner.build_runner`).
* `frozen=True` + `validate_default=True` — one immutable object, built once
  at process start via `ReloadSettings.load()`, which wraps a pydantic
  `ValidationError` into the service's own `SsmReloadError` so start-up fails
  fast with a clean one-line message instead of a raw traceback.
* Behavior change vs. the old hand-rolled parser: an invalid
  `SSM_RELOAD_POLL_INTERVAL` (non-numeric, zero, or negative) now FAILS FAST
  rather than silently falling back to 30s — a typo no longer runs the
  reloader on a surprise interval.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ssm_reload.errors import BindingError, SsmReloadError
from ssm_reload.models import ConfigRef

DEFAULT_POLL_INTERVAL = 30.0

# Where configs are projected, and the volume mounted there. Both are FIXED,
# for the same reason the label prefix is: they are one half of a contract the
# consuming stacks encode too (`env_file: /run/ssm/<project>-<config>.env`,
# `ssm-env: external: true`), and a knob is just one more way for a fleet's
# operators and its reloaders to disagree about it. What is *mounted* at the
# directory — the tmpfs volume, or a host path for a host-side compose client
# — is a deployment decision, made in the compose file, not in code.
PROJECTION_DIR = Path("/run/ssm")
PROJECTION_VOLUME = "ssm-env"

# Reverse-DNS label namespace (the Docker convention for object labels — an
# org's reverse domain avoids collisions with other tools' labels). Fixed on
# purpose: a configurable prefix would just be one more way for a fleet's
# operators and its reloaders to disagree about the control plane.
LABEL_PREFIX = "com.bearlike.ssm"
ENABLE_LABEL = f"{LABEL_PREFIX}.enable"
CONFIG_LABEL = f"{LABEL_PREFIX}.config"
REVISION_LABEL = f"{LABEL_PREFIX}.revision"
# The key names SSM injected on the last recreate. Without this, a merging
# recreate cannot tell "SSM put this variable here" from "the app has always
# had it", so a key DELETED from a config would linger in the container's
# environment forever.
KEYS_LABEL = f"{LABEL_PREFIX}.keys"
OWNER_LABEL = f"{LABEL_PREFIX}.owner"

# Labels other tools stamp on the containers THEY created. Their presence is
# the whole ownership signal: it means SSM did not create this container and
# must not take it away from whoever did. Portainer stacks are compose
# projects, so they are covered by the compose label -- there is deliberately
# no Portainer-specific handling anywhere in this service.
EXTERNAL_OWNER_LABELS = (
    "com.docker.compose.project",
    "com.docker.swarm.service.name",
)

# A RAM-backed volume, created through the Docker API so it is a first-class
# Docker object on Linux, Docker Desktop and rootless alike. Secrets written
# here never touch the host's disk, and the volume's contents exist only
# while a container holds it mounted -- so they cannot outlive the fleet.
TMPFS_VOLUME_OPTS = {
    "type": "tmpfs",
    "device": "tmpfs",
    "o": "size=8m,mode=0750",
}

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class ReloadSettings(BaseSettings):
    """Validated configuration for the ssm-reload service."""

    model_config = SettingsConfigDict(
        frozen=True,
        validate_default=True,
        populate_by_name=True,
        extra="ignore",
    )

    base_url: str = Field(
        min_length=1,
        validation_alias="SSM_BASE_URL",
        description=(
            "SSM API root the reloader polls and exports secrets from, "
            "e.g. http://ssm:5000/api."
        ),
    )
    token: SecretStr = Field(
        min_length=1,
        validation_alias="SSM_TOKEN",
        description=(
            "Read-only, scoped service token used to authenticate with "
            "the SSM API; never logged or repr'd."
        ),
    )
    poll_interval: float = Field(
        default=DEFAULT_POLL_INTERVAL,
        gt=0,
        validation_alias="SSM_RELOAD_POLL_INTERVAL",
        description=(
            "Seconds between drift-detection polls; must be positive "
            "or start-up fails fast."
        ),
    )
    log_level: LogLevel = Field(
        default="INFO",
        validation_alias="SSM_RELOAD_LOG_LEVEL",
        description="Log verbosity for the reloader's structured logs.",
    )
    otel_endpoint: str | None = Field(
        default=None,
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
        description=(
            "OTLP/HTTP endpoint to opt in to OpenTelemetry event "
            "export; unset disables telemetry entirely."
        ),
    )
    projection_configs: str = Field(
        default="",
        validation_alias="SSM_RELOAD_PROJECTION_CONFIGS",
        description=(
            "Comma-separated `project/config` pairs to project even when no "
            "container is bound to them yet — an `env_file` must exist "
            "BEFORE the first `compose up` that reads it."
        ),
    )

    @property
    def bootstrap_configs(self) -> tuple[ConfigRef, ...]:
        """`SSM_RELOAD_PROJECTION_CONFIGS` as typed coordinates."""
        return self._parse_configs(self.projection_configs)

    @staticmethod
    def _parse_configs(value: str) -> tuple[ConfigRef, ...]:
        """Parse the comma-separated list. The ONE definition of its shape.

        The field itself stays a plain string because pydantic-settings
        JSON-decodes any complex-typed field before a validator can see it,
        and a comma-separated list is not JSON.
        """
        return tuple(
            ConfigRef.parse(entry.strip())
            for entry in value.split(",")
            if entry.strip()
        )

    @field_validator("projection_configs")
    @classmethod
    def _validate_config_pairs(cls, value: str) -> str:
        # Fail fast at start-up: a typo here would otherwise surface one poll
        # interval later, as a pydantic error deep in the report path.
        try:
            cls._parse_configs(value)
        except BindingError as exc:
            raise ValueError(str(exc)) from exc
        return value

    @field_validator("base_url", "token", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        # Preserve the old parser's trim so a stray space around a URL/token
        # can't produce a "present but empty" value; emptiness is then caught
        # by the min_length constraint.
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        # Accept any case ("info", "Info", "INFO") and normalize before the
        # Literal check, so operators aren't tripped by casing.
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @classmethod
    def load(cls) -> "ReloadSettings":
        """Build settings from the environment, failing fast and clean.

        Wraps a pydantic ``ValidationError`` into ``SsmReloadError`` so the
        runner's existing error path can print one stderr line and exit
        non-zero — never a raw validation traceback.
        """
        try:
            # pydantic-settings populates every field from the environment;
            # mypy can't see that, so it reads base_url/token as missing.
            return cls()  # type: ignore[call-arg]
        except ValidationError as exc:
            parts = [
                f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            ]
            raise SsmReloadError(
                f"Invalid configuration: {'; '.join(parts)}"
            ) from exc
