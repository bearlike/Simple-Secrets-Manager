from datetime import datetime, timedelta, timezone

from bson import ObjectId

from Access.scopes import global_scopes
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

    def create_index(self, *_args, **_kwargs):
        return None

    @staticmethod
    def _is_gt(current, target):
        if current is None:
            return False
        try:
            return current > target
        except TypeError:
            return current.timestamp() > target.timestamp()

    def _match_value(self, doc, key, value):
        current = doc.get(key)
        if isinstance(value, dict):
            if "$gt" in value:
                return self._is_gt(current, value["$gt"])
            if "$exists" in value:
                return (key in doc) == bool(value["$exists"])
        return current == value

    def _match(self, doc, query):
        for key, value in query.items():
            if key == "$or":
                if not any(self._match(doc, clause) for clause in value):
                    return False
                continue
            if not self._match_value(doc, key, value):
                return False
        return True

    def find(self, query):
        return FakeCursor(
            [doc for doc in self.docs if self._match(doc, query)]
        )

    def find_one(self, query):
        for doc in self.docs:
            if self._match(doc, query):
                return doc
        return None

    def update_one(self, query, update):
        target = self.find_one(query)
        if target and "$set" in update:
            target.update(update["$set"])

    def update_many(self, query, update):
        for doc in self.docs:
            if self._match(doc, query) and "$set" in update:
                doc.update(update["$set"])

    def insert_one(self, doc):
        self.docs.append(doc)


def test_list_tokens_serializes_metadata():
    token_id = ObjectId()
    collection = FakeCollection(
        [
            {
                "_id": token_id,
                "type": "service",
                "subject_user": None,
                "subject_service_name": "api",
                "scopes": [
                    {"project_id": ObjectId(), "actions": ["secrets:read"]}
                ],
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


def test_list_tokens_hides_revoked_and_expired_by_default():
    now = datetime.now(timezone.utc)
    collection = FakeCollection(
        [
            {
                "_id": ObjectId(),
                "type": "personal",
                "revoked_at": now,
                "expires_at": now,
                "created_at": now,
            },
            {
                "_id": ObjectId(),
                "type": "personal",
                "revoked_at": None,
                "expires_at": now - timedelta(days=1),
                "created_at": now,
            },
            {
                "_id": ObjectId(),
                "type": "personal",
                "revoked_at": None,
                "expires_at": now + timedelta(days=30),
                "created_at": now,
            },
        ]
    )
    tokens = Tokens(collection)
    result = tokens.list_tokens()
    assert len(result) == 1
    all_tokens = tokens.list_tokens(include_revoked=True)
    assert len(all_tokens) == 3


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


def test_generate_personal_token_has_default_scopes():
    collection = FakeCollection([])
    tokens = Tokens(collection)
    result = tokens.generate(username="alice", max_ttl=300)

    assert result["status"] == "OK"
    assert len(collection.docs) == 1
    assert collection.docs[0]["subject_user"] == "alice"
    assert collection.docs[0]["scopes"] == global_scopes()
    actions = set(collection.docs[0]["scopes"][0]["actions"])
    assert {"projects:write", "configs:write", "secrets:write"}.issubset(
        actions
    )


def test_generate_rotates_session_tokens_and_caps_ttl():
    now = datetime.now(timezone.utc)
    collection = FakeCollection(
        [
            {
                "_id": ObjectId(),
                "type": "personal",
                "subject_user": "alice",
                "scopes": global_scopes(),
                "revoked_at": None,
                "created_at": now,
                "created_by": "alice",
            },
            {
                "_id": ObjectId(),
                "type": "personal",
                "subject_user": "alice",
                "scopes": [{"actions": ["secrets:read"]}],
                "purpose": "api",
                "revoked_at": None,
                "created_at": now,
                "created_by": "alice",
            },
        ]
    )
    tokens = Tokens(collection)
    result = tokens.generate(username="alice", max_ttl=9999999)

    assert result["status"] == "OK"
    assert collection.docs[0]["revoked_at"] is not None
    assert collection.docs[1]["revoked_at"] is None

    newest = collection.docs[-1]
    assert newest["purpose"] == "session"
    assert newest["subject_user"] == "alice"

    expires_at = newest["expires_at"]
    assert expires_at is not None
    remaining_seconds = (expires_at - datetime.utcnow()).total_seconds()
    assert 0 < remaining_seconds <= Tokens.SESSION_TOKEN_TTL_SECONDS + 2


def test_authenticate_personal_token_uses_dynamic_rbac_scopes():
    plain = "plain-token"
    collection = FakeCollection(
        [
            {
                "_id": ObjectId(),
                "type": "personal",
                "purpose": "api",
                "subject_user": "alice",
                "scopes": [{"actions": ["projects:read"]}],
                "token_hash": "",
                "revoked_at": None,
                "created_at": datetime.now(timezone.utc),
            }
        ]
    )

    def resolver(username):
        assert username == "alice"
        return {
            "scopes": [{"project_id": "p1", "actions": ["secrets:read"]}],
            "workspace_role": "collaborator",
            "workspace_id": "w1",
            "workspace_slug": "default",
            "visible_project_ids": ["p1"],
            "disabled": False,
        }

    tokens = Tokens(collection, personal_actor_resolver=resolver)
    collection.docs[0]["token_hash"] = tokens._hash_token(plain)

    actor, err = tokens.authenticate(plain)

    assert err is None
    assert actor["workspace_role"] == "collaborator"
    assert actor["workspace_slug"] == "default"
    assert actor["visible_project_ids"] == ["p1"]
    assert actor["scopes"] == [
        {"project_id": "p1", "actions": ["secrets:read"]}
    ]
    assert actor["token_scopes"] == [{"actions": ["projects:read"]}]


def test_authenticate_personal_session_token_ignores_static_token_scopes():
    plain = "plain-token-session"
    collection = FakeCollection(
        [
            {
                "_id": ObjectId(),
                "type": "personal",
                "purpose": "session",
                "subject_user": "alice",
                "scopes": [{"actions": ["projects:read"]}],
                "token_hash": "",
                "revoked_at": None,
                "created_at": datetime.now(timezone.utc),
            }
        ]
    )

    def resolver(username):
        assert username == "alice"
        return {
            "scopes": [
                {
                    "actions": [
                        "workspace:settings:read",
                        "workspace:groups:read",
                    ]
                }
            ],
            "workspace_role": "owner",
            "workspace_id": "w1",
            "workspace_slug": "default",
            "visible_project_ids": [],
            "disabled": False,
        }

    tokens = Tokens(collection, personal_actor_resolver=resolver)
    collection.docs[0]["token_hash"] = tokens._hash_token(plain)

    actor, err = tokens.authenticate(plain)

    assert err is None
    assert actor["scopes"] == [
        {"actions": ["workspace:settings:read", "workspace:groups:read"]}
    ]
    assert actor["token_scopes"] is None


def test_authenticate_legacy_personal_token_without_purpose_ignores_scopes():
    plain = "plain-token-legacy"
    collection = FakeCollection(
        [
            {
                "_id": ObjectId(),
                "type": "personal",
                "subject_user": "alice",
                "scopes": [{"actions": ["projects:read"]}],
                "token_hash": "",
                "revoked_at": None,
                "created_at": datetime.now(timezone.utc),
            }
        ]
    )

    def resolver(_username):
        return {
            "scopes": [
                {
                    "actions": [
                        "workspace:settings:read",
                        "workspace:groups:read",
                    ]
                }
            ],
            "workspace_role": "owner",
            "workspace_id": "w1",
            "workspace_slug": "default",
            "visible_project_ids": [],
            "disabled": False,
        }

    tokens = Tokens(collection, personal_actor_resolver=resolver)
    collection.docs[0]["token_hash"] = tokens._hash_token(plain)

    actor, err = tokens.authenticate(plain)

    assert err is None
    assert actor["token_scopes"] is None
    assert actor["scopes"][0]["actions"] == [
        "workspace:settings:read",
        "workspace:groups:read",
    ]


def test_authenticate_personal_token_fails_for_disabled_user():
    plain = "plain-token-2"
    collection = FakeCollection(
        [
            {
                "_id": ObjectId(),
                "type": "personal",
                "subject_user": "alice",
                "scopes": [{"actions": ["projects:read"]}],
                "token_hash": "",
                "revoked_at": None,
                "created_at": datetime.now(timezone.utc),
            }
        ]
    )

    tokens = Tokens(
        collection,
        personal_actor_resolver=lambda _username: {
            "disabled": True,
            "scopes": [],
        },
    )
    collection.docs[0]["token_hash"] = tokens._hash_token(plain)

    actor, err = tokens.authenticate(plain)

    assert actor is None
    assert err == "disabled"
