#!/usr/bin/env python3
from collections import defaultdict

from Engines.memberships import PROJECT_ROLES, WORKSPACE_ROLES

DEFAULT_WORKSPACE_ROLE = "viewer"
DEFAULT_PROJECT_ROLE = "none"

PROJECT_ROLE_RANK = {"none": 0, "viewer": 1, "collaborator": 2, "admin": 3}
WORKSPACE_ROLE_RANK = {"viewer": 1, "collaborator": 2, "admin": 3, "owner": 4}

PROJECT_ROLE_ACTIONS = {
    "none": [],
    "viewer": [
        "projects:read",
        "configs:read",
        "secrets:read",
        "secrets:export",
        "audit:read",
    ],
    "collaborator": [
        "projects:read",
        "configs:read",
        "configs:write",
        "secrets:read",
        "secrets:write",
        "secrets:export",
        "audit:read",
    ],
    "admin": [
        "projects:read",
        "configs:read",
        "configs:write",
        "secrets:read",
        "secrets:write",
        "secrets:delete",
        "secrets:export",
        "audit:read",
    ],
}

WORKSPACE_ROLE_GLOBAL_ACTIONS = {
    "viewer": ["workspace:members:read"],
    "collaborator": ["workspace:members:read"],
    "admin": sorted(
        set(
            PROJECT_ROLE_ACTIONS["admin"]
            + [
                "projects:write",
                "tokens:manage",
                "workspace:settings:read",
                "workspace:members:read",
                "workspace:groups:read",
                "workspace:groups:manage",
                "workspace:project-members:read",
                "workspace:project-members:manage",
                "workspace:mappings:read",
                "workspace:mappings:manage",
            ]
        )
    ),
    "owner": sorted(
        set(
            PROJECT_ROLE_ACTIONS["admin"]
            + [
                "projects:write",
                "tokens:manage",
                "users:manage",
                "workspace:settings:read",
                "workspace:settings:manage",
                "workspace:members:read",
                "workspace:members:manage",
                "workspace:groups:read",
                "workspace:groups:manage",
                "workspace:project-members:read",
                "workspace:project-members:manage",
                "workspace:mappings:read",
                "workspace:mappings:manage",
            ]
        )
    ),
}

WORKSPACE_DEFAULT_SETTINGS = {
    "defaultWorkspaceRole": DEFAULT_WORKSPACE_ROLE,
    "defaultProjectRole": DEFAULT_PROJECT_ROLE,
    "referencingEnabled": True,
}


class RBAC:
    ONBOARDING_DOC_ID = "bootstrap_state_v1"

    def __init__(
        self,
        workspaces_engine,
        users_engine,
        memberships_engine,
        groups_engine,
        projects_engine,
        onboarding_state_col=None,
    ):
        self._workspaces = workspaces_engine
        self._users = users_engine
        self._memberships = memberships_engine
        self._groups = groups_engine
        self._projects = projects_engine
        self._onboarding_state = onboarding_state_col

    def _bootstrap_owner_username(self):
        if self._onboarding_state is None:
            return None
        try:
            doc = (
                self._onboarding_state.find_one(
                    {"_id": self.ONBOARDING_DOC_ID}
                )
                or {}
            )
        except Exception:
            return None
        username = doc.get("initialized_by")
        return username if isinstance(username, str) and username else None

    def _ensure_user_workspace_membership(self, username):
        workspace = self._workspaces.ensure_default()
        user = self._users.ensure(username)
        workspace_id = workspace.get("_id") if workspace else None
        if workspace_id is None:
            return None, None, None

        membership = self._memberships.get_workspace_membership(
            workspace_id, username
        )
        bootstrap_owner = self._bootstrap_owner_username()
        if (
            membership
            and bootstrap_owner
            and username == bootstrap_owner
            and membership.get("workspace_role") != "owner"
        ):
            membership, _, _ = self._memberships.upsert_workspace_membership(
                workspace_id, username, "owner"
            )
        if membership:
            return workspace, user, membership

        settings = self._workspaces.get_settings(workspace_id) or {}
        role = settings.get("defaultWorkspaceRole") or DEFAULT_WORKSPACE_ROLE
        if role not in WORKSPACE_ROLES:
            role = DEFAULT_WORKSPACE_ROLE

        if bootstrap_owner and username == bootstrap_owner:
            role = "owner"
        elif self._memberships.count_workspace_members(workspace_id) == 0:
            role = "owner"
        elif not self._memberships.has_workspace_role(workspace_id, "owner"):
            role = "owner"

        membership, _, _ = self._memberships.upsert_workspace_membership(
            workspace_id, username, role
        )
        return workspace, self._users.get(username), membership

    @staticmethod
    def _project_role_max(current_role, new_role):
        if PROJECT_ROLE_RANK.get(new_role, 0) > PROJECT_ROLE_RANK.get(
            current_role, 0
        ):
            return new_role
        return current_role

    def _project_roles_for_user(self, workspace_id, username):
        group_ids = self._groups.list_user_group_ids(workspace_id, username)
        docs = self._memberships.list_project_memberships_for_subjects(
            workspace_id, username, group_ids
        )

        roles = defaultdict(lambda: "none")
        for doc in docs:
            project_id = doc.get("project_id")
            if project_id is None:
                continue
            project_role = doc.get("project_role")
            if project_role not in PROJECT_ROLES:
                continue
            roles[project_id] = self._project_role_max(
                roles[project_id], project_role
            )
        return roles

    def resolve_personal_actor(self, username):
        workspace, user, membership = self._ensure_user_workspace_membership(
            username
        )
        if workspace is None or membership is None:
            return {
                "workspace_id": None,
                "workspace_slug": None,
                "workspace_role": None,
                "scopes": [],
                "visible_project_ids": [],
                "project_roles": {},
                "disabled": False,
            }

        workspace_id = workspace.get("_id")
        workspace_role = (
            membership.get("workspace_role") or DEFAULT_WORKSPACE_ROLE
        )
        if workspace_role not in WORKSPACE_ROLES:
            workspace_role = DEFAULT_WORKSPACE_ROLE

        disabled = bool(user and user.get("disabled_at") is not None)
        if disabled:
            return {
                "workspace_id": workspace_id,
                "workspace_slug": workspace.get("slug"),
                "workspace_role": workspace_role,
                "scopes": [],
                "visible_project_ids": [],
                "project_roles": {},
                "disabled": True,
            }

        scopes = []
        visible_project_ids = []
        project_roles = {}

        global_actions = (
            WORKSPACE_ROLE_GLOBAL_ACTIONS.get(workspace_role) or []
        )
        if global_actions:
            scopes.append({"actions": list(global_actions)})

        if workspace_role in ("owner", "admin"):
            projects = self._projects.list_docs(workspace_id=workspace_id)
            for project in projects:
                project_id = project.get("_id")
                if project_id is None:
                    continue
                key = str(project_id)
                visible_project_ids.append(key)
                project_roles[key] = "admin"
        else:
            roles = self._project_roles_for_user(workspace_id, username)
            for project_id, project_role in roles.items():
                actions = PROJECT_ROLE_ACTIONS.get(project_role) or []
                if not actions:
                    continue
                project_key = str(project_id)
                scopes.append({"project_id": project_key, "actions": actions})
                visible_project_ids.append(project_key)
                project_roles[project_key] = project_role

        return {
            "workspace_id": workspace_id,
            "workspace_slug": workspace.get("slug"),
            "workspace_role": workspace_role,
            "scopes": scopes,
            "visible_project_ids": visible_project_ids,
            "project_roles": project_roles,
            "disabled": False,
        }

    @staticmethod
    def summarize_scopes(scopes):
        global_actions = set()
        project_scope_count = 0
        for scope in scopes or []:
            actions = scope.get("actions") or []
            if scope.get("project_id") or scope.get("config_id"):
                project_scope_count += 1
                continue
            for action in actions:
                global_actions.add(action)
        return {
            "globalActions": sorted(global_actions),
            "projectScopeCount": project_scope_count,
        }
