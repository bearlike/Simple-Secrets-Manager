"""Typed cross-service contracts (leaf package).

Pydantic v2 models shared verbatim by ``ssm_reload`` and ``ssm_server`` across
the HTTP boundary — the single source of truth for the reload-transparency
wire format. This package depends only on ``pydantic`` and imports no other
project package (enforced by import-linter): both sides may import it; it
imports neither.
"""

from __future__ import annotations

from ssm_contracts.reload import (
    GroupOutcome,
    ReloadConfigStatus,
    ReloadInstanceStatus,
    ReloadReport,
    ReloadUnitStatus,
    Reporter,
    Trigger,
    UnitOutcome,
    UnitStatus,
    is_valid_slug,
    summarize_validation_error,
)

__all__ = [
    "GroupOutcome",
    "ReloadConfigStatus",
    "ReloadInstanceStatus",
    "ReloadReport",
    "ReloadUnitStatus",
    "Reporter",
    "Trigger",
    "UnitOutcome",
    "UnitStatus",
    "is_valid_slug",
    "summarize_validation_error",
]

__version__ = "0.1.0"
