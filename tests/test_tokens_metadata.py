from datetime import datetime, timezone

from bson import ObjectId

from Access.tokens import Tokens


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction):
        reverse = direction == -1
        self.docs.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def __iter__(self):
        return iter(self.docs)


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def create_index(self, *args, **kwargs):
        return None

    def find(self, query):
        return FakeCursor(list(self.docs))

    def find_one(self, query):
        for doc in self.docs:
            if "_id" in query and doc.get("_id") == query["_id"]:
                return doc
            if "token_hash" in query and doc.get("token_hash") == query["token_hash"]:
                return doc
        return None

    def update_one(self, query, update):
        target = self.find_one(query)
        if target and "$set" in update:
            target.update(update["$set"])
        return None


def test_list_tokens_serializes_metadata():
    token_id = ObjectId()
    collection = FakeCollection(
        [
            {
                "_id": token_id,
                "type": "service",
                "subject_user": None,
                "subject_service_name": "api",
                "scopes": [{"project_id": ObjectId(), "actions": ["secrets:read"]}],
                "expires_at": datetime(2030, 1, 1, tzinfo=timezone.utc),
                "last_used_at": None,
                "revoked_at": None,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "created_by": "system",
            }
        ]
    )
    tokens = Tokens(collection)
    result = tokens.list_tokens()
    assert len(result) == 1
    assert result[0]["token_id"] == str(token_id)
    assert result[0]["created_at"].endswith("Z")
    assert isinstance(result[0]["scopes"][0]["project_id"], str)


def test_revoke_token_by_token_id():
    token_id = ObjectId()
    collection = FakeCollection(
        [
            {
                "_id": token_id,
                "type": "service",
                "subject_user": None,
                "created_by": "system",
                "token_hash": "unused",
                "revoked_at": None,
            }
        ]
    )
    tokens = Tokens(collection)
    result, code = tokens.revoke(token_id=str(token_id))
    assert code == 200
    assert result["status"] == "OK"
    assert collection.docs[0]["revoked_at"] is not None
