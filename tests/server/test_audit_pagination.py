from datetime import datetime, timedelta, timezone

from ssm_server.engines.audit import AuditEvents

from tests.server.fakes import FakeCollection


def test_query_events_page_returns_ordered_slice_with_has_next():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    docs = [
        {"ts": base + timedelta(minutes=i), "action": f"action-{i}"}
        for i in range(5)
    ]
    audit = AuditEvents(FakeCollection(docs))

    first_page = audit.query_events_page(limit=2, page=1)
    assert first_page["page"] == 1
    assert first_page["limit"] == 2
    assert first_page["has_next"] is True
    assert [event["action"] for event in first_page["events"]] == [
        "action-4",
        "action-3",
    ]

    third_page = audit.query_events_page(limit=2, page=3)
    assert third_page["has_next"] is False
    assert [event["action"] for event in third_page["events"]] == ["action-0"]


def test_query_events_page_applies_filters_and_since():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    docs = [
        {
            "ts": base + timedelta(minutes=1),
            "action": "a-early",
            "project_slug": "a",
        },
        {
            "ts": base + timedelta(minutes=2),
            "action": "b-mid",
            "project_slug": "b",
        },
        {
            "ts": base + timedelta(minutes=3),
            "action": "a-late",
            "project_slug": "a",
        },
    ]
    audit = AuditEvents(FakeCollection(docs))

    filtered = audit.query_events_page(
        project_slug="a", since=base + timedelta(minutes=2), limit=10, page=1
    )
    assert filtered["has_next"] is False
    assert [event["action"] for event in filtered["events"]] == ["a-late"]
