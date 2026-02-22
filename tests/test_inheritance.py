from Engines.secrets_v2 import SecretsV2


class FakeSecrets:
    def __init__(self, docs):
        self.docs = docs

    def create_index(self, *args, **kwargs):
        return None

    def find(self, query):
        return [d for d in self.docs if d["config_id"] == query["config_id"]]


class FakeConfigs:
    def __init__(self, cfgs):
        self.cfgs = cfgs

    def get_by_id(self, cfg_id):
        return self.cfgs.get(cfg_id)


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
    data, meta, msg, code = engine.export_config("child", include_parent=True, include_metadata=True)
    assert code == 200
    assert msg == "OK"
    assert data == {"A": "1", "B": "20", "C": "3"}
    assert meta["B"]["updatedAt"] is None
