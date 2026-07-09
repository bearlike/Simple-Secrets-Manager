"""Hermetic unit tests for the export ETag (no MongoDB).

Covers the pure hash helper directly on resolved value maps plus the
resolution layer, so a parent-config change is proven to flip the child's
ETag without touching the HTTP/Mongo stack.
"""

import re

from ssm_server.engines.secrets_v2 import SecretsV2, config_export_etag

ETAG_RE = re.compile(r'^"[0-9a-f]{16}"$')


class FakeSecrets:
    def __init__(self, docs):
        self.docs = docs

    def create_index(self, *_args, **_kwargs):
        return None

    def find(self, query):
        return [d for d in self.docs if d["config_id"] == query["config_id"]]

    def update_one(self, query, update, upsert=False):
        _ = upsert
        for doc in self.docs:
            if doc.get("config_id") == query.get("config_id") and doc.get(
                "key"
            ) == query.get("key"):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                return None
        return None


class FakeConfigs:
    def __init__(self, cfgs):
        self.cfgs = cfgs

    def get_by_id(self, cfg_id):
        return self.cfgs.get(cfg_id)


def test_etag_shape_is_quoted_16_hex():
    assert ETAG_RE.match(config_export_etag({"A": "1"}))


def test_etag_is_insertion_order_independent():
    assert config_export_etag({"A": "1", "B": "2"}) == config_export_etag(
        {"B": "2", "A": "1"}
    )


def test_same_values_yield_same_etag_across_representations():
    # `format`/`include_meta`/`raw` never enter the hash: a json export and
    # an env export of the same resolved map hash identically.
    resolved = {"A": "1", "B": "2"}
    assert config_export_etag(resolved) == config_export_etag(dict(resolved))


def test_value_change_flips_etag():
    assert config_export_etag({"A": "1", "B": "2"}) != config_export_etag(
        {"A": "1", "B": "20"}
    )


def test_added_key_flips_etag():
    assert config_export_etag({"A": "1"}) != config_export_etag(
        {"A": "1", "C": "3"}
    )


def _child_engine_and_docs():
    cfgs = {
        "root": {"_id": "root", "parent_config_id": None},
        "child": {"_id": "child", "parent_config_id": "root"},
    }
    docs = [
        {"config_id": "root", "key": "A", "value_enc": "1"},
        {"config_id": "child", "key": "B", "value_enc": "2"},
    ]
    return SecretsV2(FakeSecrets(docs), FakeConfigs(cfgs)), docs


def _child_etag(engine):
    data, _meta, msg, code = engine.export_config("child", include_parent=True)
    assert code == 200 and msg == "OK"
    return config_export_etag(data)


def test_parent_value_change_flips_child_etag():
    engine, docs = _child_engine_and_docs()
    before = _child_etag(engine)

    for doc in docs:
        if doc["config_id"] == "root" and doc["key"] == "A":
            doc["value_enc"] = "999"

    assert before != _child_etag(engine)
