#!/usr/bin/env python3
from datetime import datetime, timezone

from flask_restx import Resource

from Api.api import api, conn
from Api.resources.helpers import resolve_project_config
from Api.serialization import oid_to_str
from Access.is_auth import with_token, require_scope

audit_ns = api.namespace("audit", description="Audit event access")
audit_parser = api.parser()
audit_parser.add_argument("project", type=str, required=False, location="args")
audit_parser.add_argument("config", type=str, required=False, location="args")
audit_parser.add_argument("since", type=str, required=False, location="args")
audit_parser.add_argument(
    "limit", type=int, required=False, default=50, location="args"
)
audit_parser.add_argument(
    "page", type=int, required=False, default=1, location="args"
)


@audit_ns.route("/events")
class AuditEventsResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=audit_parser)
    @with_token
    def get(self):
        args = audit_parser.parse_args()
        if args["limit"] < 1:
            api.abort(400, "limit must be >= 1")
        if args["page"] < 1:
            api.abort(400, "page must be >= 1")

        project_id = None
        config_id = None
        project_slug = args.get("project")
        config_slug = args.get("config")
        if config_slug and not project_slug:
            api.abort(
                400, "project query param is required when config is provided"
            )
        if project_slug:
            project, config = resolve_project_config(project_slug, config_slug)
            project_id = project["_id"]
            config_id = config["_id"] if config else None
        require_scope("audit:read", project_id=project_id, config_id=config_id)
        since = None
        if args.get("since"):
            try:
                since = datetime.fromisoformat(
                    args["since"].replace("Z", "+00:00")
                )
                if since.tzinfo is None:
                    since = since.replace(tzinfo=timezone.utc)
            except ValueError:
                api.abort(400, "Invalid since format. Use ISO-8601 format.")
        page_result = conn.audit.query_events_page(
            project_slug=project_slug,
            config_slug=config_slug,
            since=since,
            limit=args["limit"],
            page=args["page"],
            project_id=oid_to_str(project_id),
            config_id=oid_to_str(config_id),
        )
        return {**page_result, "status": "OK"}
