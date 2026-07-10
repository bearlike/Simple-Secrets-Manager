"""Hermetic tests for the reloader fleet read model.

The ReloadStatus engine is exercised against an in-memory collection fake
(no Mongo), the pure ``group_status`` transform against plain dicts, and the
endpoint's scope gating against ``authorize`` — the resource itself needs the
Flask app and is out of scope for this hermetic suite.
"""

from __future__ import annotations

from ssm_server.access.policy import authorize
from ssm_server.access.scopes import DEFAULT_TOKEN_ACTION_SCOPES, global_scopes
from ssm_server.engines.reload_status import ReloadStatus, group_status

from tests.server.fakes import FakeCollection


def _write(engine, *, instance_id, outcome, project="web", config="prod"):
    engine.write_report(
        project_id=f"pid-{project}",
        config_id=f"cid-{project}-{config}",
        project_slug=project,
        config_slug=config,
        host="h1",
        instance_id=instance_id,
        version="0.1.0",
        trigger="poll",
        revision='"v1"',
        outcome=outcome,
        error=None,
        units=[
            {
                "id": "c1",
                "name": "c1",
                "held_revision": '"v1"',
                "outcome": "current",
                "error": None,
            }
        ],
    )


def test_write_report_upserts_on_same_key():
    col = FakeCollection()
    engine = ReloadStatus(col)

    _write(engine, instance_id="i-1", outcome="current")
    _write(engine, instance_id="i-1", outcome="updated")

    # Same (project, config, instance) overwrites — the row count tracks the
    # live fleet, not the number of heartbeats.
    assert len(col.docs) == 1
    assert col.docs[0]["outcome"] == "updated"


def test_updated_outcome_stamps_revision_updated_at():
    col = FakeCollection()
    engine = ReloadStatus(col)

    _write(engine, instance_id="i-1", outcome="updated")

    assert col.docs[0]["revision_updated_at"] is not None


def test_never_updated_instance_has_no_revision_updated_at():
    col = FakeCollection()
    engine = ReloadStatus(col)

    _write(engine, instance_id="i-1", outcome="current")

    assert col.docs[0].get("revision_updated_at") is None


def test_current_outcome_preserves_revision_updated_at():
    # Steady-state heartbeats ($set without the key) must not erase or
    # refresh the stamp -- it means "when did an actual reload last
    # happen", not "when did we last hear from the instance".
    col = FakeCollection()
    engine = ReloadStatus(col)

    _write(engine, instance_id="i-1", outcome="updated")
    stamped = col.docs[0]["revision_updated_at"]
    _write(engine, instance_id="i-1", outcome="current")

    assert col.docs[0]["outcome"] == "current"
    assert col.docs[0]["revision_updated_at"] == stamped


def test_later_updated_outcome_bumps_revision_updated_at():
    col = FakeCollection()
    engine = ReloadStatus(col)

    _write(engine, instance_id="i-1", outcome="updated")
    first = col.docs[0]["revision_updated_at"]
    _write(engine, instance_id="i-1", outcome="current")
    _write(engine, instance_id="i-1", outcome="updated")

    assert col.docs[0]["revision_updated_at"] is not None
    assert col.docs[0]["revision_updated_at"] >= first


def test_distinct_instances_produce_distinct_rows():
    col = FakeCollection()
    engine = ReloadStatus(col)

    _write(engine, instance_id="i-1", outcome="current")
    _write(engine, instance_id="i-2", outcome="current")

    assert len(col.docs) == 2


def test_query_status_filters_by_project_and_config():
    col = FakeCollection()
    engine = ReloadStatus(col)
    _write(engine, instance_id="i-1", outcome="current", config="prod")
    _write(engine, instance_id="i-1", outcome="current", config="stage")

    prod = engine.query_status(project_id="pid-web", config_id="cid-web-prod")
    assert len(prod) == 1
    assert prod[0]["config_slug"] == "prod"

    all_web = engine.query_status(project_id="pid-web")
    assert len(all_web) == 2


def test_query_status_serializes_last_seen_as_iso():
    col = FakeCollection()
    engine = ReloadStatus(col)
    _write(engine, instance_id="i-1", outcome="current")

    doc = engine.query_status()[0]
    # sanitize_doc turned the stored datetime into an ISO-8601 Z string.
    assert isinstance(doc["last_seen_at"], str)
    assert doc["last_seen_at"].endswith("Z")


def test_group_status_shapes_the_status_contract():
    docs = [
        {
            "project_slug": "web",
            "config_slug": "prod",
            "project_id": "pid",
            "config_id": "cid",
            "host": "h1",
            "instance_id": "i-1",
            "version": "0.1.0",
            "trigger": "poll",
            "revision": '"v2"',
            "outcome": "updated",
            "error": None,
            "last_seen_at": "2026-07-09T12:00:00Z",
            "revision_updated_at": "2026-07-09T11:58:00Z",
            "units": [
                {
                    "id": "c1",
                    "name": "c1",
                    "held_revision": '"v2"',
                    "outcome": "recreated",
                    "error": None,
                }
            ],
        }
    ]

    data = group_status(docs)

    assert data == [
        {
            "project": "web",
            "config": "prod",
            "instances": [
                {
                    "host": "h1",
                    "instanceId": "i-1",
                    "version": "0.1.0",
                    "lastSeenAt": "2026-07-09T12:00:00Z",
                    "revisionUpdatedAt": "2026-07-09T11:58:00Z",
                    "trigger": "poll",
                    "revision": '"v2"',
                    "outcome": "updated",
                    "error": None,
                    "units": [
                        {
                            "id": "c1",
                            "name": "c1",
                            "heldRevision": '"v2"',
                            "outcome": "recreated",
                            "error": None,
                        }
                    ],
                }
            ],
        }
    ]


def test_group_status_groups_instances_under_one_config():
    def _doc(instance):
        return {
            "project_slug": "web",
            "config_slug": "prod",
            "host": instance,
            "instance_id": instance,
            "version": "0.1.0",
            "trigger": "poll",
            "revision": '"v1"',
            "outcome": "current",
            "error": None,
            "last_seen_at": "2026-07-09T12:00:00Z",
            "units": [],
        }

    data = group_status([_doc("i-1"), _doc("i-2")])

    assert len(data) == 1
    assert {i["instanceId"] for i in data[0]["instances"]} == {"i-1", "i-2"}


def test_status_endpoint_scopes():
    # POST /reload/report gates on reload:report (service-token only); GET
    # /reload/status gates on audit:read (an admin-readable scope).
    assert "reload:report" in DEFAULT_TOKEN_ACTION_SCOPES
    assert "audit:read" in DEFAULT_TOKEN_ACTION_SCOPES
    actor = {"type": "token", "scopes": global_scopes()}
    assert authorize(actor, "reload:report", project_id="p", config_id="c")
    assert authorize(actor, "audit:read", project_id="p", config_id="c")
