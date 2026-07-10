"""Typed cross-service contract for the reload-transparency pipeline.

Single source of truth for the reload report/status wire format shared by
``ssm_reload`` (the producer) and ``ssm_server`` (the consumer). Both sides
speak these Pydantic models instead of hand-validated dicts, so the HTTP
boundary is the *only* coupling and drift surfaces as a validation error, not
a silent shape mismatch.

The wire format is camelCase (``heldRevision``, ``instanceId``,
``lastSeenAt``); Python and Mongo stay snake_case. ``populate_by_name=True``
lets each side construct by field name yet validate inbound JSON by alias, and
``extra="ignore"`` keeps version drift between reloader and server non-fatal
(unknown fields are dropped rather than rejected).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)
from pydantic.alias_generators import to_camel

# The reloader knows which of its two triggers (plus the first startup pass)
# fired the cycle; the server echoes it back in the fleet view.
Trigger = Literal["poll", "event", "startup"]
# Per-config outcome for one reporting cycle.
GroupOutcome = Literal["current", "updated", "error"]
# Per-unit outcome within a cycle.
UnitOutcome = Literal["current", "recreated", "failed", "skipped"]

# Mirrors ssm_server.engines.common.SLUG_PATTERN. Duplicated (not imported) on
# purpose so this contract stays a dependency-free leaf — keep the two in sync.
_SLUG_PATTERN = re.compile(r"^[a-z0-9_-]+$")


def is_valid_slug(value: str) -> bool:
    """True if ``value`` matches the shared project/config slug shape.

    Exposed so producers (e.g. the reloader's label parsing) can reject a
    non-slug at the boundary instead of failing later inside model
    validation. ``fullmatch`` deliberately mirrors the server's semantics —
    a trailing newline is not a slug.
    """
    return bool(_SLUG_PATTERN.fullmatch(value))


class _CamelModel(BaseModel):
    """Base for every contract model: camelCase wire, snake_case Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class Reporter(_CamelModel):
    """Identity of the reloader instance that produced a report."""

    host: str | None = None
    instance_id: str | None = None
    version: str | None = None


class UnitStatus(_CamelModel):
    """Outcome for one managed container within a reporting cycle."""

    id: str
    name: str
    held_revision: str | None = None
    outcome: UnitOutcome
    error: str | None = None


class ReloadReport(_CamelModel):
    """POST /reload/report body — one ``(project, config)`` group per cycle."""

    project: str
    config: str
    reporter: Reporter = Field(default_factory=Reporter)
    trigger: Trigger
    revision: str | None = None
    outcome: GroupOutcome
    error: str | None = None
    units: list[UnitStatus] = Field(default_factory=list)

    @field_validator("project", "config")
    @classmethod
    def _validate_slug(cls, value: str) -> str:
        if not is_valid_slug(value):
            raise ValueError("must be a slug matching ^[a-z0-9_-]+$")
        return value

    @field_validator("revision")
    @classmethod
    def _normalize_revision(cls, value: str | None) -> str | None:
        # The revision is an opaque ETag replayed verbatim by the reloader;
        # only trim incidental whitespace and treat empty as absent.
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ReloadUnitStatus(UnitStatus):
    """Per-unit status in the GET /reload/status view.

    Identical shape to the reported :class:`UnitStatus`; named separately so
    the response contract reads on its own terms.
    """


class ReloadInstanceStatus(_CamelModel):
    """One reloader instance's latest heartbeat for a single config."""

    host: str | None = None
    instance_id: str | None = None
    version: str | None = None
    # ISO-8601 string (the server sanitizes the stored datetime before it
    # reaches this model), so the wire type stays a plain string.
    last_seen_at: str | None = None
    # When this instance last ACTUALLY reloaded the config (stamped only on
    # an "updated" cycle, i.e. a real recreate) -- unlike last_seen_at,
    # which every heartbeat refreshes. Read-model only: the reloader never
    # sends it; the server derives it.
    revision_updated_at: str | None = None
    trigger: Trigger | None = None
    revision: str | None = None
    outcome: GroupOutcome | None = None
    error: str | None = None
    units: list[ReloadUnitStatus] = Field(default_factory=list)


class ReloadConfigStatus(_CamelModel):
    """GET /reload/status data item — every instance reporting on a config."""

    project: str
    config: str
    instances: list[ReloadInstanceStatus] = Field(default_factory=list)


def summarize_validation_error(exc: ValidationError) -> str:
    """Collapse a pydantic ``ValidationError`` into one readable line.

    The server maps this onto a 400 ``{"message": ...}`` envelope; the raw
    ``ValidationError`` repr is verbose and leaks internal structure, so it is
    never surfaced to clients.
    """
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ())) or "body"
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    detail = "; ".join(parts[:5])
    return (
        f"Invalid reload report: {detail}"
        if detail
        else ("Invalid reload report")
    )
