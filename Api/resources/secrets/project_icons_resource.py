#!/usr/bin/env python3
from flask_restx import Resource

from Api.core import api, conn
from Api.resources.helpers import resolve_project_config
from Access.is_auth import with_token, require_scope, audit_event

project_icons_ns = api.namespace(
    "projects/<string:project_slug>/secrets/icons",
    description="Project secret icon maintenance",
)


@project_icons_ns.route("/recompute")
class ProjectSecretIconsRecomputeResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def post(self, project_slug):
        project, _ = resolve_project_config(project_slug)
        require_scope("secrets:write", project_id=project["_id"])

        summary, msg, code = conn.secrets_v2.recompute_project_icon_slugs(
            project["_id"]
        )
        audit_event(
            "secrets.icons.recompute",
            project_slug=project_slug,
            status_code=code,
        )
        if code >= 400:
            api.abort(code, msg)
        return {"status": "OK", "summary": summary}, 200
