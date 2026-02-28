from datetime import datetime, timedelta, timezone

from Engines.audit import AuditEvents


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction):
        reverse = direction == -1
        self.docs.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def skip(self, amount):
        self.docs = self.docs[amount:]
        return self

    def limit(self, amount):
        self.docs = self.docs[:amount]
        return self

    def __iter__(self):
        return iter(self.docs)


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def create_index(self, *_args, **_kwargs):
        return None

    def _match(self, doc, query):
        for key, value in query.items():
            if key == "$and":
                if not all(self._match(doc, clause) for clause in value):
                    return False
                continue
            if key == "$or":
                if not any(self._match(doc, clause) for clause in value):
                    return False
                continue

            current = doc.get(key)
            if isinstance(value, dict) and "$gte" in value:
                if current is None or current < value["$gte"]:
                    return False
                continue
            if current != value:
                return False
        return True

    def find(self, query, projection=None):
        _ = projection
        return FakeCursor(
            [doc for doc in self.docs if self._match(doc, query)]
        )


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
