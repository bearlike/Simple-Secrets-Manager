"""The one place the API server reads its environment.

`ServerSettings` is the single, validated source of configuration for the
Flask API: every environment variable the server honors is a declared,
validated field here, and a raw `os.environ` read anywhere else in
`ssm_server/` is a defect. This exists because a scattered config surface
once let an unwanted knob ship unnoticed — one class you can read top to
bottom is the fix.

Design (two layers only: model defaults, then environment / `.env`):

* Fields carry an explicit `validation_alias` matching the EXACT env var name
  operators already set — the operator contract does not change, the reads
  just move here and gain validation (`PORT` is now an `int`, not a raw string
  handed to Flask).
* Secrets (`TOKEN_SALT`) are `SecretStr`, so no repr or log can leak them;
  unwrap with `.get_secret_value()` only at the single point of use (token
  hashing in `ssm_server.access.tokens`).
* `frozen=True` + `validate_default=True` — one immutable object, built once
  at process start (in `ssm_server.api.core`) and injected via constructors.
* This module is a LEAF inside `ssm_server`: it imports nothing from the
  package, so the hermetic test suite can import it without a live Mongo.
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Validated configuration for the Flask API server."""

    model_config = SettingsConfigDict(
        frozen=True,
        validate_default=True,
        populate_by_name=True,
        env_file=".env",
        extra="ignore",
    )

    connection_string: str = Field(
        validation_alias="CONNECTION_STRING",
        description="MongoDB connection URI used for all backend storage.",
    )
    token_salt: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="TOKEN_SALT",
        description=(
            "Salt mixed into API token hashing; never logged or repr'd."
        ),
    )
    # Comma-separated origins; kept as the raw string so the exact parsing
    # semantics live in one place (`cors_origins_list`). Declaring it as a
    # `list` field would make pydantic-settings JSON-parse the env value.
    cors_origins: str = Field(
        default="",
        validation_alias="CORS_ORIGINS",
        description=(
            "Comma-separated allowed CORS origins for direct backend "
            "access; empty falls back to flask-cors allow-all."
        ),
    )
    debug: bool = Field(
        default=False,
        validation_alias="DEBUG",
        description=(
            "Enables Flask debug mode and the auto-reloader; never "
            "enable in production."
        ),
    )
    bind_host: str = Field(
        default="0.0.0.0",
        validation_alias="BIND_HOST",
        description="Host interface the Flask server binds to.",
    )
    port: int = Field(
        default=5000,
        ge=1,
        le=65535,
        validation_alias="PORT",
        description="TCP port the Flask server listens on.",
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
        description=(
            "OTLP/HTTP endpoint to opt in to OpenTelemetry event "
            "export; unset disables telemetry entirely."
        ),
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """`CORS_ORIGINS` split on commas, trimmed, empties dropped.

        An empty list means "no explicit allow-list configured"; the caller
        (`ssm_server.api.api`) turns that into the flask-cors `"*"` default.
        """
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]
