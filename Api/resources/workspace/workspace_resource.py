#!/usr/bin/env python3
from flask import request
from flask_restx import Resource

from Api.api import api, conn
from Api.serialization import oid_to_str, to_iso
from Access.is_auth import with_token, require_scope

workspace_ns = api.namespace(
    "workspace", description="Workspace RBAC management"
)

settings_parser = api.parser()
settings_parser.add_argument(
    "defaultWorkspaceRole", type=str, required=False, location="json"
)
settings_parser.add_argument(
    "defaultProjectRole", type=str, required=False, location="json"
)
settings_parser.add_argument(
    "referencingEnabled", type=bool, required=False, location="json"
)

member_create_parser = api.parser()
member_create_parser.add_argument(
    "username", type=str, required=True, location="json"
)
member_create_parser.add_argument(
    "password", type=str, required=True, location="json"
)
member_create_parser.add_argument(
    "email", type=str, required=False, location="json"
)
member_create_parser.add_argument(
    "fullName", type=str, required=False, location="json"
)
member_create_parser.add_argument(
    "workspaceRole", type=str, required=False, location="json"
)

member_update_parser = api.parser()
member_update_parser.add_argument(
    "email", type=str, required=False, location="json"
)
member_update_parser.add_argument(
    "fullName", type=str, required=False, location="json"
)
member_update_parser.add_argument(
    "workspaceRole", type=str, required=False, location="json"
)
member_update_parser.add_argument(
    "disabled", type=bool, required=False, location="json"
)

project_member_put_parser = api.parser()
project_member_put_parser.add_argument(
    "subjectType", type=str, required=True, location="json"
)
project_member_put_parser.add_argument(
    "subjectId", type=str, required=True, location="json"
)
project_member_put_parser.add_argument(
    "role", type=str, required=True, location="json"
)

group_create_parser = api.parser()
group_create_parser.add_argument(
    "slug", type=str, required=True, location="json"
)
group_create_parser.add_argument(
    "name", type=str, required=False, location="json"
)
group_create_parser.add_argument(
    "description", type=str, required=False, location="json"
)

group_update_parser = api.parser()
group_update_parser.add_argument(
    "name", type=str, required=False, location="json"
)
group_update_parser.add_argument(
    "description", type=str, required=False, location="json"
)

group_members_put_parser = api.parser()
group_members_put_parser.add_argument(
    "add", type=list, required=False, location="json"
)
group_members_put_parser.add_argument(
    "remove", type=list, required=False, location="json"
)

mapping_create_parser = api.parser()
mapping_create_parser.add_argument(
    "provider", type=str, required=True, location="json"
)
mapping_create_parser.add_argument(
    "externalGroupKey", type=str, required=True, location="json"
)
mapping_create_parser.add_argument(
    "groupSlug", type=str, required=True, location="json"
)


def _workspace_context():
    workspace = conn.workspaces.ensure_default()
    if not workspace:
        api.abort(500, "Workspace not initialized")
    return workspace, workspace["_id"]


def _serialize_workspace_settings(workspace, settings):
    return {
        "status": "OK",
        "workspace": {
            "id": oid_to_str(workspace.get("_id")),
            "slug": workspace.get("slug"),
            "name": workspace.get("name"),
        },
        "settings": settings,
    }


def _serialize_member_row(user_doc, membership_doc):
    return {
        "username": user_doc.get("username"),
        "email": user_doc.get("email"),
        "fullName": user_doc.get("full_name"),
        "workspaceRole": membership_doc.get("workspace_role"),
        "disabled": bool(user_doc.get("disabled_at") is not None),
        "createdAt": to_iso(user_doc.get("created_at")),
    }


def _group_doc_to_payload(doc):
    return {
        "id": oid_to_str(doc.get("_id")),
        "slug": doc.get("slug"),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "createdAt": to_iso(doc.get("created_at")),
    }


def _resolve_project(project_slug):
    project = conn.projects.get_by_slug(project_slug)
    if not project:
        api.abort(404, "Project not found")
    return project


@workspace_ns.route("/settings")
class WorkspaceSettingsResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self):
        require_scope("workspace:settings:read")
        workspace, workspace_id = _workspace_context()
        settings = conn.workspaces.get_settings(workspace_id)
        return _serialize_workspace_settings(workspace, settings), 200

    @api.doc(security=["Bearer", "Token"], parser=settings_parser)
    @with_token
    def patch(self):
        require_scope("workspace:settings:manage")
        workspace, workspace_id = _workspace_context()
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            api.abort(400, "Invalid JSON payload")

        settings, msg, code = conn.workspaces.update_settings(
            workspace_id, payload
        )
        if code >= 400:
            api.abort(code, msg)

        return _serialize_workspace_settings(workspace, settings), 200


@workspace_ns.route("/members")
class WorkspaceMembersResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self):
        require_scope("workspace:members:read")
        _, workspace_id = _workspace_context()

        memberships = conn.memberships.list_workspace_memberships(workspace_id)
        users_by_username = {
            doc.get("username"): doc for doc in conn.users.list()
        }

        members = []
        for membership in memberships:
            username = membership.get("username")
            user_doc = users_by_username.get(username)
            if not user_doc:
                user_doc = conn.users.ensure(username)
            if not user_doc:
                continue
            members.append(_serialize_member_row(user_doc, membership))

        return {"status": "OK", "members": members}, 200

    @api.doc(security=["Bearer", "Token"], parser=member_create_parser)
    @with_token
    def post(self):
        require_scope("workspace:members:manage")
        _, workspace_id = _workspace_context()
        args = member_create_parser.parse_args()

        username = args["username"].strip()
        if conn.users.get(username):
            api.abort(400, "User already exists")

        userpass_status, userpass_code = conn.userpass.register(
            username=username, password=args["password"]
        )
        if userpass_code >= 400:
            api.abort(userpass_code, userpass_status)

        user, msg, code = conn.users.create(
            username, email=args.get("email"), full_name=args.get("fullName")
        )
        if code >= 400:
            conn.userpass.remove(username)
            api.abort(code, msg)

        settings = conn.workspaces.get_settings(workspace_id) or {}
        role = (
            args.get("workspaceRole")
            or settings.get("defaultWorkspaceRole")
            or "viewer"
        )
        membership, membership_msg, membership_code = (
            conn.memberships.upsert_workspace_membership(
                workspace_id, username, role
            )
        )
        if membership_code >= 400:
            conn.userpass.remove(username)
            conn.users.delete(username)
            api.abort(membership_code, membership_msg)

        return {
            "status": "OK",
            "member": _serialize_member_row(user, membership),
        }, 201


@workspace_ns.route("/members/<string:username>")
class WorkspaceMemberItemResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=member_update_parser)
    @with_token
    def patch(self, username):
        require_scope("workspace:members:manage")
        _, workspace_id = _workspace_context()

        user = conn.users.get(username)
        if not user:
            api.abort(404, "User not found")

        membership = conn.memberships.get_workspace_membership(
            workspace_id, username
        )
        if not membership:
            membership, _, _ = conn.memberships.upsert_workspace_membership(
                workspace_id, username, "viewer"
            )

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            api.abort(400, "Invalid JSON payload")

        if "email" in payload or "fullName" in payload:
            _, msg, code = conn.users.update_profile(
                username,
                email=payload.get("email") if "email" in payload else None,
                full_name=payload.get("fullName")
                if "fullName" in payload
                else None,
            )
            if code >= 400:
                api.abort(code, msg)

        if "disabled" in payload:
            if not isinstance(payload.get("disabled"), bool):
                api.abort(400, "disabled must be boolean")
            _, msg, code = conn.users.set_disabled(
                username, payload.get("disabled")
            )
            if code >= 400:
                api.abort(code, msg)

        if "workspaceRole" in payload:
            membership, msg, code = (
                conn.memberships.upsert_workspace_membership(
                    workspace_id,
                    username,
                    payload.get("workspaceRole"),
                )
            )
            if code >= 400:
                api.abort(code, msg)

        user = conn.users.get(username)
        membership = conn.memberships.get_workspace_membership(
            workspace_id, username
        )
        return {
            "status": "OK",
            "member": _serialize_member_row(user, membership),
        }, 200

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def delete(self, username):
        require_scope("workspace:members:manage")
        _, workspace_id = _workspace_context()

        user = conn.users.get(username)
        if not user:
            api.abort(404, "User not found")

        _, msg, code = conn.users.set_disabled(username, True)
        if code >= 400:
            api.abort(code, msg)

        membership = conn.memberships.get_workspace_membership(
            workspace_id, username
        )
        return {
            "status": "OK",
            "member": _serialize_member_row(
                conn.users.get(username), membership
            ),
        }, 200


@workspace_ns.route("/projects/<string:project_slug>/members")
class WorkspaceProjectMembersResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self, project_slug):
        require_scope("workspace:project-members:read")
        _, workspace_id = _workspace_context()
        project = _resolve_project(project_slug)
        memberships = conn.memberships.list_project_memberships(
            workspace_id, project["_id"]
        )

        items = []
        for item in memberships:
            subject_type = item.get("subject_type")
            subject_id = item.get("subject_id")
            payload = {
                "subjectType": subject_type,
                "subjectId": subject_id,
                "role": item.get("project_role"),
            }
            if subject_type == "group":
                group = conn.groups.get_by_id(workspace_id, subject_id)
                payload["groupSlug"] = group.get("slug") if group else None
            items.append(payload)

        return {"status": "OK", "members": items}, 200

    @api.doc(security=["Bearer", "Token"], parser=project_member_put_parser)
    @with_token
    def put(self, project_slug):
        require_scope("workspace:project-members:manage")
        _, workspace_id = _workspace_context()
        project = _resolve_project(project_slug)
        args = project_member_put_parser.parse_args()

        subject_type = args["subjectType"]
        subject_id = args["subjectId"]
        role = args["role"]

        if subject_type == "user":
            if not conn.users.get(subject_id):
                api.abort(404, "User not found")
            membership_subject_id = subject_id
        elif subject_type == "group":
            group = conn.groups.get_by_slug(workspace_id, subject_id)
            if not group:
                api.abort(404, "Group not found")
            membership_subject_id = str(group.get("_id"))
        else:
            api.abort(400, "subjectType must be user or group")

        _, msg, code = conn.memberships.upsert_project_membership(
            workspace_id,
            project["_id"],
            subject_type,
            membership_subject_id,
            role,
        )
        if code >= 400:
            api.abort(code, msg)

        return {"status": "OK"}, 200


@workspace_ns.route(
    "/projects/<string:project_slug>/members/<string:subject_type>/<string:subject_id>"
)
class WorkspaceProjectMemberItemResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def delete(self, project_slug, subject_type, subject_id):
        require_scope("workspace:project-members:manage")
        _, workspace_id = _workspace_context()
        project = _resolve_project(project_slug)

        membership_subject_id = subject_id
        if subject_type == "group":
            group = conn.groups.get_by_slug(workspace_id, subject_id)
            if group:
                membership_subject_id = str(group.get("_id"))

        msg, code = conn.memberships.remove_project_membership(
            workspace_id,
            project["_id"],
            subject_type,
            membership_subject_id,
        )
        if code >= 400:
            api.abort(code, msg)
        return {"status": "OK"}, 200


@workspace_ns.route("/groups")
class WorkspaceGroupsResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self):
        require_scope("workspace:groups:read")
        _, workspace_id = _workspace_context()
        groups = conn.groups.list_groups(workspace_id)
        return {
            "status": "OK",
            "groups": [_group_doc_to_payload(doc) for doc in groups],
        }, 200

    @api.doc(security=["Bearer", "Token"], parser=group_create_parser)
    @with_token
    def post(self):
        require_scope("workspace:groups:manage")
        _, workspace_id = _workspace_context()
        args = group_create_parser.parse_args()

        group, msg, code = conn.groups.create_group(
            workspace_id,
            slug=args["slug"],
            name=args.get("name"),
            description=args.get("description"),
        )
        if code >= 400:
            api.abort(code, msg)
        return {"status": "OK", "group": _group_doc_to_payload(group)}, 201


@workspace_ns.route("/groups/<string:group_slug>")
class WorkspaceGroupItemResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=group_update_parser)
    @with_token
    def patch(self, group_slug):
        require_scope("workspace:groups:manage")
        _, workspace_id = _workspace_context()
        args = group_update_parser.parse_args()

        group, msg, code = conn.groups.update_group(
            workspace_id,
            group_slug,
            name=args.get("name"),
            description=args.get("description"),
        )
        if code >= 400:
            api.abort(code, msg)
        return {"status": "OK", "group": _group_doc_to_payload(group)}, 200

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def delete(self, group_slug):
        require_scope("workspace:groups:manage")
        _, workspace_id = _workspace_context()
        msg, code = conn.groups.delete_group(workspace_id, group_slug)
        if code >= 400:
            api.abort(code, msg)
        return {"status": "OK"}, 200


@workspace_ns.route("/groups/<string:group_slug>/members")
class WorkspaceGroupMembersResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self, group_slug):
        require_scope("workspace:groups:read")
        _, workspace_id = _workspace_context()
        group = conn.groups.get_by_slug(workspace_id, group_slug)
        if not group:
            api.abort(404, "Group not found")
        members = conn.groups.list_group_members(workspace_id, group["_id"])
        return {
            "status": "OK",
            "members": [
                doc.get("username") for doc in members if doc.get("username")
            ],
        }, 200

    @api.doc(security=["Bearer", "Token"], parser=group_members_put_parser)
    @with_token
    def put(self, group_slug):
        require_scope("workspace:groups:manage")
        _, workspace_id = _workspace_context()
        args = group_members_put_parser.parse_args()

        add = args.get("add") or []
        remove = args.get("remove") or []
        for username in add:
            if not conn.users.get(username):
                api.abort(404, f"User not found: {username}")

        members, msg, code = conn.groups.update_group_members(
            workspace_id,
            group_slug,
            add=add,
            remove=remove,
        )
        if code >= 400:
            api.abort(code, msg)

        return {
            "status": "OK",
            "members": [
                doc.get("username") for doc in members if doc.get("username")
            ],
        }, 200


@workspace_ns.route("/group-mappings")
class WorkspaceGroupMappingsResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self):
        require_scope("workspace:mappings:read")
        _, workspace_id = _workspace_context()
        mappings = conn.groups.list_group_mappings(workspace_id)

        payload = []
        for mapping in mappings:
            group = conn.groups.get_by_id(
                workspace_id, mapping.get("group_id")
            )
            payload.append(
                {
                    "id": oid_to_str(mapping.get("_id")),
                    "provider": mapping.get("provider"),
                    "externalGroupKey": mapping.get("external_group_key"),
                    "groupSlug": group.get("slug") if group else None,
                    "createdAt": to_iso(mapping.get("created_at")),
                }
            )
        return {"status": "OK", "mappings": payload}, 200

    @api.doc(security=["Bearer", "Token"], parser=mapping_create_parser)
    @with_token
    def post(self):
        require_scope("workspace:mappings:manage")
        _, workspace_id = _workspace_context()
        args = mapping_create_parser.parse_args()

        mapping, msg, code = conn.groups.create_group_mapping(
            workspace_id,
            provider=args["provider"],
            external_group_key=args["externalGroupKey"],
            group_slug=args["groupSlug"],
        )
        if code >= 400:
            api.abort(code, msg)

        group = conn.groups.get_by_id(workspace_id, mapping.get("group_id"))
        return {
            "status": "OK",
            "mapping": {
                "id": oid_to_str(mapping.get("_id")),
                "provider": mapping.get("provider"),
                "externalGroupKey": mapping.get("external_group_key"),
                "groupSlug": group.get("slug") if group else None,
            },
        }, 201


@workspace_ns.route("/group-mappings/<string:mapping_id>")
class WorkspaceGroupMappingItemResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def delete(self, mapping_id):
        require_scope("workspace:mappings:manage")
        _, workspace_id = _workspace_context()
        msg, code = conn.groups.delete_group_mapping(workspace_id, mapping_id)
        if code >= 400:
            api.abort(code, msg)
        return {"status": "OK"}, 200
