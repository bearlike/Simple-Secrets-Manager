from datetime import datetime, timezone

from bson import ObjectId

from Engines.configs import Configs


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction):
        reverse = direction == -1
        self.docs.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __iter__(self):
        return iter(self.docs)


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def create_index(self, *args, **kwargs):
        return None

    def find(self, query, projection):
        project_id = query.get("project_id")
        docs = [doc for doc in self.docs if doc.get("project_id") == project_id]
        return FakeCursor(list(docs))

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if query.get("_id") == doc.get("_id") and query.get("project_id") == doc.get("project_id"):
                return doc
        return None


def test_configs_list_returns_frontend_shape():
    parent_id = ObjectId()
    child_id = ObjectId()
    collection = FakeCollection(
        [
            {
                "_id": parent_id,
                "project_id": "p1",
                "slug": "base",
                "name": "Base",
                "parent_config_id": None,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            },
            {
                "_id": child_id,
                "project_id": "p1",
                "slug": "dev",
                "name": "Dev",
                "parent_config_id": parent_id,
                "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            },
        ]
    )
    configs = Configs(collection)
    result = configs.list("p1")
    assert result == [
        {"slug": "base", "name": "Base", "parentSlug": None, "createdAt": "2026-01-01T00:00:00Z"},
        {"slug": "dev", "name": "Dev", "parentSlug": "base", "createdAt": "2026-01-02T00:00:00Z"},
    ]


def test_configs_list_raw_returns_internal_shape_with_limit():
    parent_id = ObjectId()
    child_id = ObjectId()
    collection = FakeCollection(
        [
            {
                "_id": parent_id,
                "project_id": "p1",
                "slug": "base",
                "name": "Base",
                "parent_config_id": None,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            },
            {
                "_id": child_id,
                "project_id": "p1",
                "slug": "dev",
                "name": "Dev",
                "parent_config_id": parent_id,
                "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            },
        ]
    )
    configs = Configs(collection)
    result = configs.list_raw("p1", limit=1)
    assert len(result) == 1
    assert result[0]["_id"] == parent_id
    assert result[0]["slug"] == "base"
    assert result[0]["parent_config_id"] is None
