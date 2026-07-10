from ssm_server.engines.secrets_v2 import SecretsV2

from tests.server.fakes import FakeConfigs, FakeSecrets


def test_export_merge_child_overrides_parent():
    cfgs = {
        "root": {"_id": "root", "parent_config_id": None},
        "child": {"_id": "child", "parent_config_id": "root"},
    }
    docs = [
        {"config_id": "root", "key": "A", "value_enc": "1"},
        {"config_id": "root", "key": "B", "value_enc": "2"},
        {"config_id": "child", "key": "B", "value_enc": "20"},
        {"config_id": "child", "key": "C", "value_enc": "3"},
    ]
    engine = SecretsV2(FakeSecrets(docs), FakeConfigs(cfgs))
    data, meta, msg, code = engine.export_config(
        "child", include_parent=True, include_metadata=True
    )
    assert code == 200
    assert msg == "OK"
    assert data == {"A": "1", "B": "20", "C": "3"}
    assert meta["B"]["updatedAt"] is None
