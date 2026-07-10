"""Hermetic tests for export provenance + env annotations (no MongoDB).

``include_provenance`` tags each key with the config slug that supplied the
effective value and whether it was inherited; the flag lives only in ``meta``
so default (non-provenance) output stays byte-identical.
"""

from ssm_server.engines.secrets_v2 import SecretsV2

from tests.server.fakes import FakeConfigs, FakeSecrets


def _three_level(docs):
    cfgs = {
        "root": {
            "_id": "root",
            "project_id": "p1",
            "slug": "root",
            "parent_config_id": None,
        },
        "mid": {
            "_id": "mid",
            "project_id": "p1",
            "slug": "mid",
            "parent_config_id": "root",
        },
        "leaf": {
            "_id": "leaf",
            "project_id": "p1",
            "slug": "leaf",
            "parent_config_id": "mid",
        },
    }
    return SecretsV2(FakeSecrets(docs), FakeConfigs(cfgs))


def test_provenance_source_and_is_inherited_across_three_levels():
    docs = [
        {"config_id": "root", "key": "A", "value_enc": "a"},
        {"config_id": "root", "key": "B", "value_enc": "b-root"},
        {"config_id": "mid", "key": "B", "value_enc": "b-mid"},
        {"config_id": "leaf", "key": "C", "value_enc": "c"},
        {"config_id": "root", "key": "D", "value_enc": "d-root"},
        {"config_id": "leaf", "key": "D", "value_enc": "d-leaf"},
    ]
    engine = _three_level(docs)
    data, meta, msg, code = engine.export_config(
        "leaf", include_parent=True, include_provenance=True
    )
    assert code == 200 and msg == "OK"
    assert data["B"] == "b-mid"
    assert data["D"] == "d-leaf"
    assert meta["A"]["source"] == "root"
    assert meta["A"]["isInherited"] is True
    assert meta["B"]["source"] == "mid"
    assert meta["B"]["isInherited"] is True
    assert meta["C"]["source"] == "leaf"
    assert meta["C"]["isInherited"] is False
    assert meta["D"]["source"] == "leaf"
    assert meta["D"]["isInherited"] is False


def test_default_export_meta_has_no_provenance_keys():
    docs = [{"config_id": "root", "key": "A", "value_enc": "a"}]
    engine = _three_level(docs)
    _, meta, _, _ = engine.export_config(
        "leaf", include_parent=True, include_metadata=True
    )
    assert "source" not in meta["A"]
    assert "isInherited" not in meta["A"]


def test_export_without_meta_or_provenance_returns_none_meta():
    docs = [{"config_id": "root", "key": "A", "value_enc": "a"}]
    engine = _three_level(docs)
    data, meta, _, _ = engine.export_config("leaf", include_parent=True)
    assert data == {"A": "a"}
    assert meta is None


def test_to_env_default_output_is_byte_identical():
    data = {"A": "1", "B": "2"}
    blob, msg, code = SecretsV2.to_env(data)
    assert code == 200 and msg == "OK"
    assert blob == "A=1\nB=2"
    # Passing no annotations must match the annotation-free rendering exactly.
    assert SecretsV2.to_env(data, None)[0] == blob
    assert SecretsV2.to_env(data, {})[0] == blob


def test_to_env_annotations_prepend_comment_lines():
    data = {"A": "1", "B": "2"}
    annotations = {"A": "# from root: base env"}
    blob, _, code = SecretsV2.to_env(data, annotations)
    assert code == 200
    assert blob == "# from root: base env\nA=1\nB=2"


def test_to_env_annotation_newlines_cannot_inject_env_lines():
    # Descriptions are operator-editable and flow into annotations; a
    # crafted "desc\nINJECTED=evil" must never become its own env line.
    data = {"A": "1"}
    annotations = {"A": "# from root: desc\nINJECTED=evil\r\nMORE=x"}
    blob, _, code = SecretsV2.to_env(data, annotations)
    assert code == 200
    assert "\r" not in blob  # a lone CR is a line break to some parsers
    lines = blob.split("\n")
    assert lines[-1] == "A=1"
    # Everything before the KEY=VALUE line stays a single comment line.
    assert len(lines) == 2
    assert lines[0].startswith("#")
    assert "INJECTED=evil" in lines[0]  # flattened into the comment
