#!/usr/bin/env python3
"""Fleet read model for reloader status heartbeats.

One document per ``(project_id, config_id, instance_id)`` — the latest
heartbeat from each ``ssm-reload`` instance about each config it manages. The
reloader stays stateless; this collection is the *server-side* view it POSTs
into once per cycle (every poll, including 304 steady-state).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ssm_contracts import ReloadConfigStatus, ReloadInstanceStatus
from ssm_server.api.serialization import sanitize_doc

# 7 days. WHY: the upsert key already bounds LIVE cardinality to the fleet size
# (one doc per reloader instance per config), so unbounded growth is not the
# problem this TTL solves. It reaps DEAD instances — a reloader that stopped
# heartbeating (host decommissioned, container removed) ages out on its own, so
# the fleet view self-heals instead of showing ghosts forever. (The audit
# collection's unbounded growth is a known gap we are deliberately not
# repeating here.)
STATUS_TTL_SECONDS = 7 * 24 * 60 * 60


class ReloadStatus:
    """Latest per-instance reload status, keyed (project, config, instance)."""

    def __init__(self, status_col: Any) -> None:
        self._status = status_col
        # UPSERT key: one row per reloader instance per config.
        self._status.create_index(
            [("project_id", 1), ("config_id", 1), ("instance_id", 1)],
            unique=True,
        )
        # TTL reaper (see STATUS_TTL_SECONDS).
        self._status.create_index(
            "last_seen_at", expireAfterSeconds=STATUS_TTL_SECONDS
        )

    def write_report(
        self,
        *,
        project_id: str,
        config_id: str,
        project_slug: str,
        config_slug: str,
        host: str | None,
        instance_id: str | None,
        version: str | None,
        trigger: str | None,
        revision: str | None,
        outcome: str | None,
        error: str | None,
        units: list[dict[str, Any]],
    ) -> None:
        """UPSERT one reloader instance's latest heartbeat for one config.

        Keyed on ``(project_id, config_id, instance_id)`` so repeated reports
        from the same instance overwrite rather than accumulate — the row count
        tracks the live fleet, not the report volume.
        """
        key = {
            "project_id": project_id,
            "config_id": config_id,
            "instance_id": instance_id,
        }
        doc = {
            **key,
            "project_slug": project_slug,
            "config_slug": config_slug,
            "host": host,
            "version": version,
            "trigger": trigger,
            "revision": revision,
            "outcome": outcome,
            "error": error,
            "units": units,
            "last_seen_at": datetime.now(timezone.utc),
        }
        if outcome == "updated":
            # "updated" means a recreate actually happened this cycle (the
            # reloader pins that semantics), so stamp WHEN. Steady-state
            # cycles omit the key and $set leaves the prior stamp intact --
            # the field answers "when did the last real reload happen", not
            # "when did we last hear from the instance" (last_seen_at).
            doc["revision_updated_at"] = datetime.now(timezone.utc)
        self._status.update_one(key, {"$set": doc}, upsert=True)

    def query_status(
        self,
        project_id: str | None = None,
        config_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return sanitized per-instance docs, newest heartbeat first."""
        query: dict[str, Any] = {}
        if project_id is not None:
            query["project_id"] = project_id
        if config_id is not None:
            query["config_id"] = config_id
        docs = list(
            self._status.find(query, {"_id": 0}).sort("last_seen_at", -1)
        )
        return [sanitize_doc(doc) for doc in docs]


def group_status(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group per-instance docs into the GET /reload/status contract shape.

    Snake_case Mongo docs in, camelCase JSON out — built through the shared
    ``ssm_contracts`` response models so the wire shape has one source of
    truth. ``populate_by_name`` lets each snake_case doc validate directly,
    and ``extra="ignore"`` drops the grouping-only keys (``project_id`` etc.).
    """
    grouped: dict[tuple[str, str], ReloadConfigStatus] = {}
    for doc in docs:
        project = doc.get("project_slug") or ""
        config = doc.get("config_slug") or ""
        key = (project, config)
        cfg = grouped.get(key)
        if cfg is None:
            cfg = ReloadConfigStatus(project=project, config=config)
            grouped[key] = cfg
        cfg.instances.append(ReloadInstanceStatus.model_validate(doc))
    return [cfg.model_dump(by_alias=True) for cfg in grouped.values()]
