from datetime import datetime, timezone

from Engines.rbac import RBAC


class WorkspacesStub:
    def __init__(self):
        self.workspace = {"_id": "w1", "slug": "default", "name": "Default"}
        self.settings = {
            "defaultWorkspaceRole": "viewer",
            "defaultProjectRole": "none",
            "referencingEnabled": True,
        }

    def ensure_default(self):
        return self.workspace

    def get_settings(self, workspace_id):
        if workspace_id != "w1":
            return None
        return dict(self.settings)


class UsersStub:
    def __init__(self):
        self.docs = {}

    def ensure(self, username):
        self.docs.setdefault(
            username,
            {
                "username": username,
                "disabled_at": None,
                "created_at": datetime.now(timezone.utc),
            },
        )
        return self.docs[username]

    def get(self, username):
        return self.docs.get(username)


class MembershipsStub:
    def __init__(self):
        self.workspace_memberships = {}
        self.project_memberships = []

    def get_workspace_membership(self, workspace_id, username):
        return self.workspace_memberships.get((workspace_id, username))

    def count_workspace_members(self, workspace_id):
        return len(
            [1 for key in self.workspace_memberships if key[0] == workspace_id]
        )

    def has_workspace_role(self, workspace_id, workspace_role):
        return any(
            value.get("workspace_role") == workspace_role
            for (
                member_workspace_id,
                _,
            ), value in self.workspace_memberships.items()
            if member_workspace_id == workspace_id
        )

    def upsert_workspace_membership(
        self, workspace_id, username, workspace_role
    ):
        doc = {
            "workspace_id": workspace_id,
            "username": username,
            "workspace_role": workspace_role,
        }
        self.workspace_memberships[(workspace_id, username)] = doc
        return doc, "OK", 200

    def list_project_memberships_for_subjects(
        self, workspace_id, username, group_ids
    ):
        resolved = []
        for doc in self.project_memberships:
            if doc.get("workspace_id") != workspace_id:
                continue
            if (
                doc.get("subject_type") == "user"
                and doc.get("subject_id") == username
            ):
                resolved.append(doc)
                continue
            if doc.get("subject_type") == "group" and doc.get(
                "subject_id"
            ) in set(group_ids or []):
                resolved.append(doc)
        return resolved


class GroupsStub:
    def __init__(self):
        self.user_groups = {}

    def list_user_group_ids(self, workspace_id, username):
        return list(self.user_groups.get((workspace_id, username), []))


class ProjectsStub:
    def __init__(self, docs):
        self.docs = docs

    def list_docs(self, workspace_id=None):
        _ = workspace_id
        return list(self.docs)


class OnboardingStateStub:
    def __init__(self, initialized_by=None):
        self.initialized_by = initialized_by

    def find_one(self, query):
        if query.get("_id") != "bootstrap_state_v1":
            return None
        if self.initialized_by is None:
            return {}
        return {"initialized_by": self.initialized_by}


def _build_rbac(initialized_by=None):
    workspaces = WorkspacesStub()
    users = UsersStub()
    memberships = MembershipsStub()
    groups = GroupsStub()
    projects = ProjectsStub([{"_id": "p1"}, {"_id": "p2"}])
    onboarding_state = OnboardingStateStub(initialized_by=initialized_by)
    engine = RBAC(
        workspaces,
        users,
        memberships,
        groups,
        projects,
        onboarding_state_col=onboarding_state,
    )
    return engine, users, memberships, groups


def test_first_workspace_member_becomes_owner():
    engine, _, memberships, _ = _build_rbac()

    actor = engine.resolve_personal_actor("alice")

    assert actor["workspace_role"] == "owner"
    assert "users:manage" in actor["scopes"][0]["actions"]
    assert set(actor["visible_project_ids"]) == {"p1", "p2"}
    assert (
        memberships.get_workspace_membership("w1", "alice")["workspace_role"]
        == "owner"
    )


def test_collaborator_uses_highest_role_from_direct_and_group_members():
    engine, users, memberships, groups = _build_rbac()
    users.ensure("alice")
    memberships.upsert_workspace_membership("w1", "alice", "collaborator")
    groups.user_groups[("w1", "alice")] = ["g1"]
    memberships.project_memberships = [
        {
            "workspace_id": "w1",
            "project_id": "p1",
            "subject_type": "user",
            "subject_id": "alice",
            "project_role": "viewer",
        },
        {
            "workspace_id": "w1",
            "project_id": "p1",
            "subject_type": "group",
            "subject_id": "g1",
            "project_role": "admin",
        },
        {
            "workspace_id": "w1",
            "project_id": "p2",
            "subject_type": "group",
            "subject_id": "g1",
            "project_role": "none",
        },
    ]

    actor = engine.resolve_personal_actor("alice")

    assert actor["workspace_role"] == "collaborator"
    assert actor["visible_project_ids"] == ["p1"]
    assert actor["project_roles"]["p1"] == "admin"
    scope = next(
        item for item in actor["scopes"] if item.get("project_id") == "p1"
    )
    assert scope["project_id"] == "p1"
    assert "secrets:delete" in scope["actions"]


def test_disabled_user_has_no_scopes():
    engine, users, memberships, _ = _build_rbac()
    users.docs["alice"] = {
        "username": "alice",
        "disabled_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    memberships.upsert_workspace_membership("w1", "alice", "viewer")

    actor = engine.resolve_personal_actor("alice")

    assert actor["disabled"] is True
    assert actor["scopes"] == []
    assert actor["visible_project_ids"] == []


def test_bootstrap_user_is_owner_even_when_members_already_exist():
    engine, users, memberships, _ = _build_rbac(initialized_by="admin")
    memberships.upsert_workspace_membership("w1", "other", "owner")
    users.ensure("admin")

    actor = engine.resolve_personal_actor("admin")

    assert actor["workspace_role"] == "owner"
    assert "users:manage" in actor["scopes"][0]["actions"]


def test_viewer_gets_workspace_members_read_scope():
    engine, users, memberships, _ = _build_rbac()
    memberships.upsert_workspace_membership("w1", "owner-user", "owner")
    users.ensure("alice")

    actor = engine.resolve_personal_actor("alice")

    assert actor["workspace_role"] == "viewer"
    assert any(
        "workspace:members:read" in (scope.get("actions") or [])
        and scope.get("project_id") is None
        for scope in actor["scopes"]
    )
