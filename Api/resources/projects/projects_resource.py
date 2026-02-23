#!/usr/bin/env python3
from flask_restx import Resource, fields
from flask import g

from Api.api import api, conn
from Access.is_auth import with_token, require_scope

projects_ns = api.namespace("projects", description="Project management")
project_model = api.model(
    "Project",
    {
        "slug": fields.String(required=True),
        "name": fields.String(required=True),
    },
)
project_create_parser = api.parser()
project_create_parser.add_argument("slug", type=str, required=True, location="json")
project_create_parser.add_argument("name", type=str, required=False, location="json")


@projects_ns.route("")
class ProjectsResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self):
        require_scope("projects:read")
        return {"projects": conn.projects.list()}

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
        return {"status": "OK", "project": {"slug": result["slug"], "name": result["name"]}}, 201
