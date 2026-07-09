#!/usr/bin/env python3
from flask import request
from flask_restx import Resource

from ssm_server.api.core import api
from ssm_server.api.resources.helpers import resolve_project_config
from ssm_server.access.is_auth import with_token, require_scope, audit_event

reload_ns = api.namespace("reload", description="Secrets reload reporting")
reload_parser = api.parser()
reload_parser.add_argument("project", type=str, required=True, location="json")
reload_parser.add_argument("config", type=str, required=True, location="json")
reload_parser.add_argument(
    "container", type=str, required=False, location="json"
)
reload_parser.add_argument("host", type=str, required=False, location="json")
reload_parser.add_argument(
    "from_revision", type=str, required=False, location="json"
)
reload_parser.add_argument(
    "to_revision", type=str, required=False, location="json"
)


def _optional_string(value):
    """Coerce an optional field to ``str`` or ``None`` for the audit log."""
    return value if isinstance(value, str) else None


@reload_ns.route("/events")
class ReloadEventsResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=reload_parser)
    @with_token
    def post(self):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            api.abort(400, "Request body must be a JSON object")
        project_slug = payload.get("project")
        config_slug = payload.get("config")
        if not isinstance(project_slug, str) or not project_slug:
            api.abort(400, "project is required")
        if not isinstance(config_slug, str) or not config_slug:
            api.abort(400, "config is required")
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope(
            "reload:report",
            project_id=project["_id"],
            config_id=config["_id"],
        )
        audit_event(
            "reload.applied",
            project_slug=project_slug,
            config_slug=config_slug,
            container=_optional_string(payload.get("container")),
            host=_optional_string(payload.get("host")),
            from_revision=_optional_string(payload.get("from_revision")),
            to_revision=_optional_string(payload.get("to_revision")),
            status_code=200,
        )
        return {"status": "OK"}, 200
