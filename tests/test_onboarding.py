from Access.onboarding import Onboarding
from pymongo.errors import DuplicateKeyError


class FakeStateCollection:
    def __init__(self):
        self.docs = {}

    def create_index(self, *args, **kwargs):
        return None

    def find_one(self, query):
        doc_id = query.get("_id")
        if doc_id is None:
            return None
        return self.docs.get(doc_id)

    def insert_one(self, doc):
        doc_id = doc.get("_id")
        if doc_id in self.docs:
            raise DuplicateKeyError("duplicate key")
        self.docs[doc_id] = dict(doc)
        return None

    def update_one(self, query, update):
        doc_id = query.get("_id")
        if doc_id not in self.docs:
            self.docs[doc_id] = {"_id": doc_id}
        target = self.docs[doc_id]
        for key, value in update.get("$set", {}).items():
            target[key] = value
        for key in update.get("$unset", {}).keys():
            target.pop(key, None)
        return None


class FakeUserPass:
    def __init__(self):
        self.users = {}

    def register(self, username, password):
        if username in self.users:
            return "User already exist", 400
        self.users[username] = password
        return {"status": "OK"}, 200

    def is_authorized(self, username, password):
        return self.users.get(username) == password


class FakeTokens:
    def __init__(self):
        self.calls = 0

    def create_token(
        self,
        token_type,
        created_by,
        scopes,
        subject_user=None,
        subject_service_name=None,
        expires_at=None,
    ):
        self.calls += 1
        username = subject_user or created_by or "user"
        return {
            "token": f"token-{username}",
            "status": "OK",
            "expires_at": None,
            "type": token_type,
            "scopes": scopes,
            "subject_service_name": subject_service_name,
        }


def test_onboarding_status_default_not_initialized():
    onboarding = Onboarding(FakeStateCollection(), FakeUserPass(), FakeTokens())
    state = onboarding.get_state()
    assert state["isInitialized"] is False
    assert state["state"] == "not_initialized"


def test_bootstrap_success_and_lock_after_completion():
    onboarding = Onboarding(FakeStateCollection(), FakeUserPass(), FakeTokens())
    result, code = onboarding.bootstrap("admin", "password", issue_token=True)
    assert code == 201
    assert result["status"] == "OK"
    assert result["token"] == "token-admin"
    assert result["onboarding"]["isInitialized"] is True

    second_result, second_code = onboarding.bootstrap("admin2", "password2", issue_token=True)
    assert second_code == 409
    assert second_result["status"] == "System already initialized"
