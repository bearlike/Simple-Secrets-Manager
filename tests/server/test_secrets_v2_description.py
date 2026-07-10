"""Hermetic tests for the optional per-secret ``description`` annotation.

Description is metadata: it round-trips through ``put`` into the secret doc
and surfaces in export ``meta``, but never enters the resolved value map (so
the value-only export ETag the reloader polls cannot flip on it -- see
``test_config_export_etag.py``).
"""

from ssm_server.engines.secrets_v2 import SecretsV2

from tests.server.fakes import FakeConfigs, FakeSecrets


def _engine_with_docs(docs):
    cfgs = {
        "cfg": {"_id": "cfg", "project_id": "p1", "parent_config_id": None}
    }
    return SecretsV2(FakeSecrets(docs), FakeConfigs(cfgs))


def test_put_persists_description():
    engine = _engine_with_docs([])
    _, code = engine.put(
        "cfg",
        "DATABASE_URL",
        "postgres://",
        "actor",
        description="Primary Postgres DSN",
        description_provided=True,
    )
    assert code == 200
    assert engine._secrets.docs[0]["description"] == "Primary Postgres DSN"


def test_put_preserves_description_when_omitted():
    # An icon/value/sensitivity edit that omits description must not wipe it.
    docs = [
        {
            "config_id": "cfg",
            "key": "DATABASE_URL",
            "value_enc": "v",
            "description": "keep me",
        }
    ]
    engine = _engine_with_docs(docs)
    _, code = engine.put("cfg", "DATABASE_URL", "next", "actor")
    assert code == 200
    assert docs[0]["description"] == "keep me"


def test_put_empty_description_clears_it():
    docs = [
        {
            "config_id": "cfg",
            "key": "DATABASE_URL",
            "value_enc": "v",
            "description": "old note",
        }
    ]
    engine = _engine_with_docs(docs)
    _, code = engine.put(
        "cfg",
        "DATABASE_URL",
        "next",
        "actor",
        description="",
        description_provided=True,
    )
    assert code == 200
    assert docs[0]["description"] == ""


def test_put_rejects_non_string_description():
    engine = _engine_with_docs([])
    message, code = engine.put(
        "cfg",
        "DATABASE_URL",
        "v",
        "actor",
        description=123,
        description_provided=True,
    )
    assert code == 400
    assert message == "description must be a string"


def test_export_meta_includes_description():
    docs = [
        {
            "config_id": "cfg",
            "key": "DATABASE_URL",
            "value_enc": "v",
            "icon_slug": "mdi:database",
            "description": "Primary DSN",
        }
    ]
    engine = _engine_with_docs(docs)
    _, meta, _, code = engine.export_config(
        "cfg", include_parent=True, include_metadata=True
    )
    assert code == 200
    assert meta["DATABASE_URL"]["description"] == "Primary DSN"


def test_export_meta_description_defaults_empty():
    docs = [
        {
            "config_id": "cfg",
            "key": "DATABASE_URL",
            "value_enc": "v",
            "icon_slug": "mdi:database",
        }
    ]
    engine = _engine_with_docs(docs)
    _, meta, _, code = engine.export_config(
        "cfg", include_parent=True, include_metadata=True
    )
    assert code == 200
    assert meta["DATABASE_URL"]["description"] == ""
