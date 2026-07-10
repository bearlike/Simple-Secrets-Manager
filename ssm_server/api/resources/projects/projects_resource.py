#!/usr/bin/env python3
from flask_restx import Resource, fields, inputs
from flask import g

from ssm_server.api.core import api, conn
from ssm_server.api.resources.helpers import resolve_project_config
from ssm_server.access.is_auth import (
    with_token,
    require_scope,
    audit_event,
)
from ssm_server.access.policy import authorize

projects_ns = api.namespace("projects", description="Project management")
project_model = api.model(
    "Project",
    {
        "slug": fields.String(required=True),
        "name": fields.String(required=True),
        "description": fields.String(),
        "archived": fields.Boolean(),
    },
)
projects_list_parser = api.parser()
projects_list_parser.add_argument(
    "archived", type=inputs.boolean, default=False, location="args"
)
project_create_parser = api.parser()
project_create_parser.add_argument(
    "slug", type=str, required=True, location="json"
)
project_create_parser.add_argument(
    "name", type=str, required=False, location="json"
)
project_create_parser.add_argument(
    "description", type=str, required=False, location="json"
)
project_update_parser = api.parser()
project_update_parser.add_argument(
    "name", type=str, required=False, location="json"
)
project_update_parser.add_argument(
    "archived", type=inputs.boolean, required=False, location="json"
)
project_update_parser.add_argument(
    "description",
    type=str,
    required=False,
    location="json",
    store_missing=False,
)


@projects_ns.route("")
class ProjectsResource(Resource):
    @staticmethod
    def _has_global_projects_read(actor):
        for scope in actor.get("scopes") or []:
            actions = set(scope.get("actions") or [])
            if "projects:read" not in actions:
                continue
            if scope.get("project_id") or scope.get("config_id"):
                continue
            return True
        return False

    @staticmethod
    def _visible_project_ids_from_actor(actor):
        if actor.get("token_type") == "personal":
            return list(actor.get("visible_project_ids") or [])

        project_ids = set()
        for scope in actor.get("scopes") or []:
            project_id = scope.get("project_id")
            actions = set(scope.get("actions") or [])
            if project_id is None:
                continue
            if actions.intersection(
                {
                    "projects:read",
                    "configs:read",
                    "secrets:read",
                    "secrets:export",
                }
            ):
                project_ids.add(str(project_id))
        return list(project_ids)

    @api.doc(security=["Bearer", "Token"], parser=projects_list_parser)
    @with_token
    def get(self):
        args = projects_list_parser.parse_args()
        actor = g.actor
        workspace_role = actor.get("workspace_role")
        workspace_id = actor.get("workspace_id")

        if workspace_role in (
            "owner",
            "admin",
        ) or self._has_global_projects_read(actor):
            candidate_docs = conn.projects.list_docs(workspace_id=workspace_id)
        else:
            visible_project_ids = self._visible_project_ids_from_actor(actor)
            if not visible_project_ids:
                return {"projects": []}
            candidate_docs = conn.projects.list_by_ids(visible_project_ids)
            if workspace_id is not None:
                candidate_docs = [
                    doc
                    for doc in candidate_docs
                    if doc.get("workspace_id") in (None, workspace_id)
                ]

        authorized_project_ids = [
            str(doc.get("_id"))
            for doc in candidate_docs
            if doc.get("_id") is not None
            and authorize(actor, "projects:read", project_id=doc.get("_id"))
        ]
        if not authorized_project_ids:
            return {"projects": []}
        return {
            "projects": conn.projects.list(
                workspace_id=workspace_id,
                project_ids=authorized_project_ids,
                archived=args["archived"],
            )
        }

    @api.doc(security=["Bearer", "Token"], parser=project_create_parser)
    @with_token
    def post(self):
        require_scope("projects:write")
        args = project_create_parser.parse_args()
        result, code = conn.projects.create(
            args["slug"], args.get("name"), description=args.get("description")
        )
        if code >= 400:
            api.abort(code, result)
        audit_event(
            "projects.write",
            project_slug=result.get("slug"),
            status_code=201,
        )
        return {
            "status": "OK",
            "project": {
                "slug": result["slug"],
                "name": result["name"],
                "description": result.get("description"),
                "archived": bool(result.get("archived", False)),
            },
        }, 201


@projects_ns.route("/<string:project_slug>")
class ProjectItemResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=project_update_parser)
    @with_token
    def patch(self, project_slug):
        require_scope("projects:write")
        args = project_update_parser.parse_args()
        result, code = conn.projects.update(
            project_slug,
            name=args.get("name"),
            archived=args.get("archived"),
            description=args.get("description"),
        )
        if code >= 400:
            api.abort(code, result)
        audit_event(
            "projects.write",
            project_slug=result.get("slug"),
            status_code=200,
        )
        return {
            "status": "OK",
            "project": {
                "slug": result.get("slug"),
                "name": result.get("name"),
                "description": result.get("description"),
                "archived": bool(result.get("archived", False)),
            },
        }, 200

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def delete(self, project_slug):
        require_scope("projects:write")
        project, _ = resolve_project_config(project_slug)

        config_ids = conn.configs.list_ids(project["_id"])
        conn.secrets_v2.delete_by_configs(config_ids)
        conn.configs.delete_all_for_project(project["_id"])

        workspace_id = project.get("workspace_id") or g.actor.get(
            "workspace_id"
        )
        if workspace_id is not None:
            conn.memberships.remove_all_for_project(
                workspace_id, project["_id"]
            )
        conn.projects.delete(project["slug"])
        audit_event(
            "projects.delete",
            project_slug=project.get("slug"),
            status_code=200,
        )
        return {"status": "OK"}, 200
