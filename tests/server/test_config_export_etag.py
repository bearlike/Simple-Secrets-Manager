"""Hermetic unit tests for the export ETag (no MongoDB).

Covers the pure hash helper directly on resolved value maps plus the
resolution layer, so a parent-config change is proven to flip the child's
ETag without touching the HTTP/Mongo stack.
"""

import re

from ssm_server.engines.secrets_v2 import SecretsV2, config_export_etag

from tests.server.fakes import FakeConfigs, FakeSecrets

ETAG_RE = re.compile(r'^"[0-9a-f]{16}"$')


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


def test_sensitivity_toggle_does_not_flip_etag():
    # Sensitivity lives in meta, never in the resolved value map -- toggling
    # it must not change the value-only hash (the reloader's 304 divergence
    # check would false-positive otherwise).
    engine, docs = _child_engine_and_docs()
    before = _child_etag(engine)
    for doc in docs:
        doc["sensitive"] = not doc.get("sensitive", True)
    assert before == _child_etag(engine)


def test_config_description_change_does_not_flip_etag():
    # A config-level description is off the value map entirely.
    engine, _docs = _child_engine_and_docs()
    before = _child_etag(engine)
    engine._configs.cfgs["child"]["description"] = "changed"
    assert before == _child_etag(engine)


def test_value_only_tag_is_unchanged_by_default_meta_arg():
    # meta=None reproduces the value-only tag byte-for-byte, so the reloader
    # path (and the revisions it has already stored) is unaffected.
    values = {"A": "1", "B": "2"}
    assert config_export_etag(values) == config_export_etag(values, None)


def test_meta_representation_folds_into_etag():
    # The console requests include_meta/include_provenance, so its body carries
    # per-key metadata. A metadata-only change (icon slug, description,
    # sensitivity, updatedAt) MUST flip the meta-inclusive tag even though the
    # value map is untouched -- otherwise the browser's conditional refetch
    # 304s and keeps rendering the pre-edit icon. Regression guard for the
    # stale-icon / stale-sensitive no-op.
    values = {"A": "1"}
    meta_before = {"A": {"iconSlug": "simple-icons:org", "description": ""}}
    meta_after = {"A": {"iconSlug": "mdi:database", "description": ""}}
    assert config_export_etag(values, meta_before) != config_export_etag(
        values, meta_after
    )


def test_meta_tag_differs_from_value_only_tag():
    # The value-only representation (reloader) and the meta representation
    # (console) are distinct; their tags must differ so a client that cached
    # one never satisfies a conditional request for the other.
    values = {"A": "1"}
    meta = {"A": {"iconSlug": "mdi:database", "description": "primary db"}}
    assert config_export_etag(values) != config_export_etag(values, meta)


def _child_meta_etag(engine):
    data, meta, msg, code = engine.export_config(
        "child", include_parent=True, include_metadata=True
    )
    assert code == 200 and msg == "OK"
    return config_export_etag(data, meta)


def test_icon_edit_flips_meta_etag_but_not_value_only_etag():
    # End-to-end at the engine layer: a manual icon edit leaves the value-only
    # tag (reloader) identical but flips the meta tag (console) -- exactly what
    # busts the browser cache so the table shows the new icon instead of a
    # stale 304.
    engine, _docs = _child_engine_and_docs()
    value_before = _child_etag(engine)
    meta_before = _child_meta_etag(engine)
    engine.put(
        "child",
        "B",
        "2",
        "actor",
        icon_slug="mdi:database",
        icon_slug_provided=True,
    )
    assert value_before == _child_etag(engine)
    assert meta_before != _child_meta_etag(engine)
