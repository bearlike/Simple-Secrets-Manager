from datetime import datetime, timezone

from ssm_server.engines.secrets_v2 import SecretsV2

from tests.server.fakes import FakeConfigs, FakeSecrets


def test_compare_key_across_configs_resolves_inherited_and_missing():
    docs = [
        {
            "config_id": "base",
            "key": "API_HOST",
            "value_enc": "base.example.com",
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_by": "system",
        },
        {
            "config_id": "prod",
            "key": "API_HOST",
            "value_enc": "prod.example.com",
            "updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "updated_by": "alice",
        },
    ]
    configs = [
        {"_id": "base", "slug": "base", "parent_config_id": None},
        {"_id": "dev", "slug": "dev", "parent_config_id": "base"},
        {"_id": "prod", "slug": "prod", "parent_config_id": "base"},
        {"_id": "qa", "slug": "qa", "parent_config_id": None},
    ]

    engine = SecretsV2(FakeSecrets(docs), FakeConfigs({}))
    rows, msg, code = engine.compare_key_across_configs(
        configs,
        "API_HOST",
        include_parent=True,
        include_metadata=True,
        include_empty=True,
    )

    assert code == 200
    assert msg == "OK"
    assert rows == [
        {
            "configId": "base",
            "configSlug": "base",
            "effective": {
                "value": "base.example.com",
                "source": "base",
                "isInherited": False,
                "sensitive": True,
            },
            "direct": {
                "exists": True,
                "value": "base.example.com",
                "sensitive": True,
            },
            "meta": {
                "updatedAt": "2026-01-01T00:00:00Z",
                "updatedBy": "system",
                "iconSlug": "",
                "description": "",
            },
        },
        {
            "configId": "dev",
            "configSlug": "dev",
            "effective": {
                "value": "base.example.com",
                "source": "base",
                "isInherited": True,
                "sensitive": True,
            },
            "direct": {"exists": False, "value": None},
            "meta": {
                "updatedAt": "2026-01-01T00:00:00Z",
                "updatedBy": "system",
                "iconSlug": "",
                "description": "",
            },
        },
        {
            "configId": "prod",
            "configSlug": "prod",
            "effective": {
                "value": "prod.example.com",
                "source": "prod",
                "isInherited": False,
                "sensitive": True,
            },
            "direct": {
                "exists": True,
                "value": "prod.example.com",
                "sensitive": True,
            },
            "meta": {
                "updatedAt": "2026-01-02T00:00:00Z",
                "updatedBy": "alice",
                "iconSlug": "",
                "description": "",
            },
        },
        {
            "configId": "qa",
            "configSlug": "qa",
            "effective": {
                "value": None,
                "source": None,
                "isInherited": False,
                "sensitive": True,
            },
            "direct": {"exists": False, "value": None},
            "meta": {
                "updatedAt": None,
                "updatedBy": None,
                "iconSlug": "",
                "description": "",
            },
        },
    ]


def test_compare_key_across_configs_skips_missing_when_include_empty_false():
    docs = [
        {
            "config_id": "base",
            "key": "API_HOST",
            "value_enc": "base.example.com",
        },
    ]
    configs = [
        {"_id": "base", "slug": "base", "parent_config_id": None},
        {"_id": "dev", "slug": "dev", "parent_config_id": "base"},
        {"_id": "qa", "slug": "qa", "parent_config_id": None},
    ]
    engine = SecretsV2(FakeSecrets(docs), FakeConfigs({}))
    rows, msg, code = engine.compare_key_across_configs(
        configs,
        "API_HOST",
        include_parent=True,
        include_metadata=False,
        include_empty=False,
    )

    assert code == 200
    assert msg == "OK"
    assert rows == [
        {
            "configId": "base",
            "configSlug": "base",
            "effective": {
                "value": "base.example.com",
                "source": "base",
                "isInherited": False,
                "sensitive": True,
            },
            "direct": {
                "exists": True,
                "value": "base.example.com",
                "sensitive": True,
            },
        },
        {
            "configId": "dev",
            "configSlug": "dev",
            "effective": {
                "value": "base.example.com",
                "source": "base",
                "isInherited": True,
                "sensitive": True,
            },
            "direct": {"exists": False, "value": None},
        },
    ]


def test_compare_key_across_configs_handles_inheritance_cycle():
    docs = []
    configs = [
        {"_id": "a", "slug": "a", "parent_config_id": "b"},
        {"_id": "b", "slug": "b", "parent_config_id": "a"},
    ]
    engine = SecretsV2(FakeSecrets(docs), FakeConfigs({}))
    rows, msg, code = engine.compare_key_across_configs(
        configs,
        "BROKEN",
        include_parent=True,
        include_metadata=False,
        include_empty=True,
    )
    assert rows is None
    assert code == 400
    assert msg == "Config inheritance cycle detected"


def test_compare_key_across_configs_rejects_invalid_key():
    engine = SecretsV2(FakeSecrets([]), FakeConfigs({}))
    rows, msg, code = engine.compare_key_across_configs(
        [], "not-valid", include_parent=True
    )
    assert rows is None
    assert code == 400
    assert msg == "Invalid secret key"


def test_compare_key_across_configs_respects_include_parent_false():
    docs = [
        {
            "config_id": "base",
            "key": "API_HOST",
            "value_enc": "base.example.com",
        },
    ]
    configs = [
        {"_id": "base", "slug": "base", "parent_config_id": None},
        {"_id": "dev", "slug": "dev", "parent_config_id": "base"},
    ]
    engine = SecretsV2(FakeSecrets(docs), FakeConfigs({}))

    rows, msg, code = engine.compare_key_across_configs(
        configs,
        "API_HOST",
        include_parent=False,
        include_metadata=False,
        include_empty=False,
    )

    assert code == 200
    assert msg == "OK"
    assert rows == [
        {
            "configId": "base",
            "configSlug": "base",
            "effective": {
                "value": "base.example.com",
                "source": "base",
                "isInherited": False,
                "sensitive": True,
            },
            "direct": {
                "exists": True,
                "value": "base.example.com",
                "sensitive": True,
            },
        },
    ]


def test_compare_key_across_configs_ignores_malformed_config_entries():
    configs = [
        {"_id": "valid", "slug": "valid", "parent_config_id": "missing"},
        {"_id": None, "slug": "bad"},
        {"_id": "bad-slug", "slug": 123},
    ]
    engine = SecretsV2(FakeSecrets([]), FakeConfigs({}))

    rows, msg, code = engine.compare_key_across_configs(
        configs,
        "API_HOST",
        include_parent=True,
        include_metadata=False,
        include_empty=True,
    )

    assert code == 200
    assert msg == "OK"
    assert rows == [
        {
            "configId": "valid",
            "configSlug": "valid",
            "effective": {
                "value": None,
                "source": None,
                "isInherited": False,
                "sensitive": True,
            },
            "direct": {"exists": False, "value": None},
        }
    ]
