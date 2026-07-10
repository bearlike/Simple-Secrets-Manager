from ssm_server.access.onboarding import Onboarding

from tests.server.fakes import FakeCollection


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
        _ = expires_at
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


class FakeWorkspaces:
    def __init__(self):
        self.workspace = {"_id": "w1", "slug": "default"}

    def ensure_default(self):
        return self.workspace


class FakeUsers:
    def __init__(self):
        self.docs = {}

    def ensure(self, username):
        self.docs[username] = {"username": username}
        return self.docs[username]


class FakeMemberships:
    def __init__(self):
        self.last_call = None

    def upsert_workspace_membership(self, workspace_id, username, role):
        self.last_call = (workspace_id, username, role)
        return {"workspace_role": role}, "OK", 200


def test_onboarding_status_default_not_initialized():
    onboarding = Onboarding(FakeCollection(), FakeUserPass(), FakeTokens())
    state = onboarding.get_state()
    assert state["isInitialized"] is False
    assert state["state"] == "not_initialized"


def test_bootstrap_success_and_lock_after_completion():
    onboarding = Onboarding(FakeCollection(), FakeUserPass(), FakeTokens())
    result, code = onboarding.bootstrap("admin", "password", issue_token=True)
    assert code == 201
    assert result["status"] == "OK"
    assert result["token"] == "token-admin"
    assert result["onboarding"]["isInitialized"] is True

    second_result, second_code = onboarding.bootstrap(
        "admin2", "password2", issue_token=True
    )
    assert second_code == 409
    assert second_result["status"] == "System already initialized"


def test_bootstrap_seeds_workspace_owner_membership():
    workspaces = FakeWorkspaces()
    users = FakeUsers()
    memberships = FakeMemberships()
    onboarding = Onboarding(
        FakeCollection(),
        FakeUserPass(),
        FakeTokens(),
        workspaces_engine=workspaces,
        users_engine=users,
        memberships_engine=memberships,
    )

    result, code = onboarding.bootstrap("admin", "password", issue_token=False)

    assert code == 200
    assert result["status"] == "OK"
    assert users.docs["admin"]["username"] == "admin"
    assert memberships.last_call == ("w1", "admin", "owner")
