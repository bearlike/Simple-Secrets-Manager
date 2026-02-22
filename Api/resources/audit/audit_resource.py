#!/usr/bin/env python3
from datetime import datetime

from flask_restx import Resource

from Api.api import api, conn
from Api.resources.helpers import resolve_project_config
from Access.is_auth import with_token, require_scope

audit_ns = api.namespace("audit", description="Audit event access")
audit_parser = api.parser()
audit_parser.add_argument("project", type=str, required=False, location="args")
audit_parser.add_argument("config", type=str, required=False, location="args")
audit_parser.add_argument("since", type=str, required=False, location="args")
audit_parser.add_argument("limit", type=int, required=False, default=100, location="args")


@audit_ns.route("/events")
class AuditEventsResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=audit_parser)
    @with_token
    def get(self):
        args = audit_parser.parse_args()
        project_id = None
        config_id = None
        if args.get("project"):
            project, config = resolve_project_config(args["project"], args.get("config"))
            project_id = project["_id"]
            config_id = config["_id"] if config else None
        require_scope("audit:read", project_id=project_id, config_id=config_id)
        since = datetime.fromisoformat(args["since"]) if args.get("since") else None
        events = conn.audit.query_events(project_id=project_id, config_id=config_id, since=since, limit=args["limit"])
        return {"events": events, "status": "OK"}
