import warnings

from Engines.kv import Key_Value_Secrets


class FakeKVCollection:
    def __init__(self):
        self.docs = {"service": {"path": "service", "data": {"A": "1"}}}

    def find_one(self, query):
        return self.docs.get(query.get("path"))

    def insert_one(self, doc):
        self.docs[doc["path"]] = doc

    def update_one(self, query, update):
        doc = self.docs.get(query.get("path"))
        if not doc:
            return None
        for key, value in update.get("$set", {}).items():
            _, field = key.split(".", 1)
            doc["data"][field] = value
        for key in update.get("$unset", {}):
            _, field = key.split(".", 1)
            doc["data"].pop(field, None)


def _messages_for(callable_obj):
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        callable_obj()
    return [str(record.message) for record in records]


def test_kv_methods_emit_deprecation_warnings():
    engine = Key_Value_Secrets(FakeKVCollection())
    messages = []
    messages.extend(_messages_for(lambda: engine.get("service", "A")))
    messages.extend(_messages_for(lambda: engine.add("service", "B", "2")))
    messages.extend(_messages_for(lambda: engine.update("service", "A", "9")))
    messages.extend(_messages_for(lambda: engine.delete("service", "B")))

    assert any("deprecated" in message.lower() for message in messages)
    assert any(
        "/api/projects/{project}/configs/{config}/secrets/{key}" in message
        for message in messages
    )
