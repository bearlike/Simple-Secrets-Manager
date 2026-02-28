from datetime import datetime, timedelta

from Access.tokens import Tokens


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def create_index(self, *_args, **_kwargs):
        return None

    def find_one(self, query):
        for doc in self.docs:
            if doc.get("token_hash") == query.get("token_hash"):
                return doc
        return None

    def update_one(self, query, update):
        _ = (query, update)


def test_expired_token_is_rejected():
    token = "abc"
    temp = Tokens(FakeCollection([]))
    hashed = temp._hash_token(token)
    collection = FakeCollection(
        [
            {
                "_id": "1",
                "token_hash": hashed,
                "type": "service",
                "expires_at": datetime.utcnow() - timedelta(seconds=1),
                "revoked_at": None,
                "scopes": [],
            }
        ]
    )
    tokens = Tokens(collection)
    actor, err = tokens.authenticate(token)
    assert actor is None
    assert err == "expired"
