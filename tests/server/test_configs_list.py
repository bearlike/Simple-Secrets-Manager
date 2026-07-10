from datetime import datetime, timezone

from bson import ObjectId

from ssm_server.engines.configs import Configs

from tests.server.fakes import FakeCollection


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
        {
            "slug": "base",
            "name": "Base",
            "parentSlug": None,
            "description": None,
            "createdAt": "2026-01-01T00:00:00Z",
        },
        {
            "slug": "dev",
            "name": "Dev",
            "parentSlug": "base",
            "description": None,
            "createdAt": "2026-01-02T00:00:00Z",
        },
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
