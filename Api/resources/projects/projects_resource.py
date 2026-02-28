#!/usr/bin/env python3
from flask_restx import Resource, fields
from flask import g

from Api.core import api, conn
from Access.is_auth import with_token, require_scope
from Access.policy import authorize

projects_ns = api.namespace("projects", description="Project management")
project_model = api.model(
    "Project",
    {
        "slug": fields.String(required=True),
        "name": fields.String(required=True),
    },
)
project_create_parser = api.parser()
project_create_parser.add_argument(
    "slug", type=str, required=True, location="json"
)
project_create_parser.add_argument(
    "name", type=str, required=False, location="json"
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

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self):
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
                workspace_id=workspace_id, project_ids=authorized_project_ids
            )
        }

    @api.doc(security=["Bearer", "Token"], parser=project_create_parser)
    @with_token
    def post(self):
        require_scope("projects:write")
        args = project_create_parser.parse_args()
        result, code = conn.projects.create(args["slug"], args.get("name"))
        if code >= 400:
            api.abort(code, result)
        conn.audit.write_event(
            {
                "actor_type": "token",
                "actor_id": g.actor.get("id"),
                "token_id": g.actor.get("token_id"),
                "action": "projects.write",
                "project_slug": result.get("slug"),
                "method": "POST",
                "path": "/api/projects",
                "status_code": 201,
                "latency_ms": 0,
            }
        )
        return {
            "status": "OK",
            "project": {"slug": result["slug"], "name": result["name"]},
        }, 201
