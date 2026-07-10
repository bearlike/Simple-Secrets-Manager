"""Hermetic tests for the per-key sensitivity flag (no MongoDB).

Covers the default-sensitive contract (absence of the field reads as
sensitive), preserve-on-update, and the most-restrictive-wins merge across an
inheritance chain -- a child can never un-hide a key an ancestor marks
sensitive.
"""

from ssm_server.engines.secrets_v2 import SecretsV2

from tests.server.fakes import FakeConfigs, FakeSecrets


def _engine(docs=None):
    cfgs = {
        "cfg": {"_id": "cfg", "project_id": "p1", "parent_config_id": None}
    }
    return SecretsV2(FakeSecrets(docs or []), FakeConfigs(cfgs))


def _chain_engine(docs):
    cfgs = {
        "root": {
            "_id": "root",
            "project_id": "p1",
            "slug": "root",
            "parent_config_id": None,
        },
        "child": {
            "_id": "child",
            "project_id": "p1",
            "slug": "child",
            "parent_config_id": "root",
        },
    }
    return SecretsV2(FakeSecrets(docs), FakeConfigs(cfgs))


def test_create_defaults_sensitive_true():
    engine = _engine()
    payload, code = engine.put("cfg", "API_KEY", "secret", "actor")
    assert code == 200
    assert payload["sensitive"] is True
    assert engine._secrets.docs[0]["sensitive"] is True


def test_get_legacy_doc_reads_sensitive_true():
    docs = [{"config_id": "cfg", "key": "API_KEY", "value_enc": "v"}]
    engine = _engine(docs)
    result, code = engine.get("cfg", "API_KEY")
    assert code == 200
    assert result["sensitive"] is True


def test_put_explicit_non_sensitive():
    engine = _engine()
    payload, code = engine.put(
        "cfg",
        "PUBLIC_URL",
        "https://x",
        "actor",
        sensitive=False,
        sensitive_provided=True,
    )
    assert code == 200
    assert payload["sensitive"] is False
    assert engine._secrets.docs[0]["sensitive"] is False


def test_update_preserves_sensitive_flag_when_omitted():
    engine = _engine()
    engine.put(
        "cfg",
        "PUBLIC_URL",
        "v1",
        "actor",
        sensitive=False,
        sensitive_provided=True,
    )
    payload, code = engine.put("cfg", "PUBLIC_URL", "v2", "actor")
    assert code == 200
    assert payload["sensitive"] is False
    assert engine._secrets.docs[0]["sensitive"] is False
    assert engine._secrets.docs[0]["value_enc"] == "v2"


def test_put_rejects_non_bool_sensitive():
    engine = _engine()
    message, code = engine.put(
        "cfg",
        "API_KEY",
        "v",
        "actor",
        sensitive="yes",
        sensitive_provided=True,
    )
    assert code == 400
    assert message == "sensitive must be a boolean"


def test_effective_sensitive_true_when_parent_sensitive_child_not():
    docs = [
        {"config_id": "root", "key": "K", "value_enc": "r", "sensitive": True},
        {
            "config_id": "child",
            "key": "K",
            "value_enc": "c",
            "sensitive": False,
        },
    ]
    engine = _chain_engine(docs)
    _, meta, _, code = engine.export_config(
        "child", include_parent=True, include_metadata=True
    )
    assert code == 200
    # Child un-hiding its own doc cannot widen exposure of an ancestor's key.
    assert meta["K"]["sensitive"] is True


def test_effective_sensitive_true_when_child_more_restrictive():
    docs = [
        {
            "config_id": "root",
            "key": "K",
            "value_enc": "r",
            "sensitive": False,
        },
        {
            "config_id": "child",
            "key": "K",
            "value_enc": "c",
            "sensitive": True,
        },
    ]
    engine = _chain_engine(docs)
    _, meta, _, _ = engine.export_config(
        "child", include_parent=True, include_metadata=True
    )
    assert meta["K"]["sensitive"] is True


def test_effective_non_sensitive_only_when_all_false():
    docs = [
        {
            "config_id": "root",
            "key": "K",
            "value_enc": "r",
            "sensitive": False,
        },
        {
            "config_id": "child",
            "key": "K",
            "value_enc": "c",
            "sensitive": False,
        },
    ]
    engine = _chain_engine(docs)
    _, meta, _, _ = engine.export_config(
        "child", include_parent=True, include_metadata=True
    )
    assert meta["K"]["sensitive"] is False


def test_legacy_missing_flag_is_sensitive_in_export():
    docs = [{"config_id": "child", "key": "K", "value_enc": "c"}]
    engine = _chain_engine(docs)
    _, meta, _, _ = engine.export_config(
        "child", include_parent=True, include_metadata=True
    )
    assert meta["K"]["sensitive"] is True


def test_compare_effective_sensitive_most_restrictive():
    docs = [
        {"config_id": "root", "key": "K", "value_enc": "r", "sensitive": True},
        {
            "config_id": "child",
            "key": "K",
            "value_enc": "c",
            "sensitive": False,
        },
    ]
    cfgs = [
        {"_id": "root", "slug": "root", "parent_config_id": None},
        {"_id": "child", "slug": "child", "parent_config_id": "root"},
    ]
    engine = _chain_engine(docs)
    rows, _, code = engine.compare_key_across_configs(
        cfgs,
        "K",
        include_parent=True,
        include_metadata=False,
        include_empty=True,
    )
    assert code == 200
    by_slug = {row["configSlug"]: row for row in rows}
    # Child's own doc is non-sensitive, but its effective value is masked
    # because the inherited ancestor is sensitive.
    assert by_slug["child"]["direct"]["sensitive"] is False
    assert by_slug["child"]["effective"]["sensitive"] is True
    assert by_slug["root"]["effective"]["sensitive"] is True


def test_compare_truncated_chain_fails_closed():
    # The compare set is authorization-filtered/truncated: when a config's
    # parent chain extends beyond the set handed in, sensitivity must fail
    # CLOSED — an unseen ancestor may mark the key sensitive, and a child
    # must never render unmasked just because that ancestor is out of view.
    docs = [
        {"config_id": "root", "key": "K", "value_enc": "r", "sensitive": True},
        {
            "config_id": "child",
            "key": "K",
            "value_enc": "c",
            "sensitive": False,
        },
    ]
    # Only the child is in the compared set; root exists but is not visible.
    cfgs = [{"_id": "child", "slug": "child", "parent_config_id": "root"}]
    engine = _chain_engine(docs)
    rows, _, code = engine.compare_key_across_configs(
        cfgs,
        "K",
        include_parent=True,
        include_metadata=False,
        include_empty=True,
    )
    assert code == 200
    (row,) = rows
    assert row["effective"]["sensitive"] is True


def test_single_get_reports_effective_sensitivity():
    # get() must agree with the export meta: the child's own doc says
    # non-sensitive, but a sensitive ancestor doc wins over the full chain.
    docs = [
        {"config_id": "root", "key": "K", "value_enc": "r", "sensitive": True},
        {
            "config_id": "child",
            "key": "K",
            "value_enc": "c",
            "sensitive": False,
        },
    ]
    engine = _chain_engine(docs)
    payload, code = engine.get("child", "K")
    assert code == 200
    assert payload["value"] == "c"
    assert payload["sensitive"] is True


def test_single_get_non_sensitive_when_whole_chain_agrees():
    docs = [
        {
            "config_id": "child",
            "key": "K",
            "value_enc": "c",
            "sensitive": False,
        },
    ]
    engine = _chain_engine(docs)
    payload, code = engine.get("child", "K")
    assert code == 200
    assert payload["sensitive"] is False
