#!/usr/bin/env python3
from datetime import datetime, timedelta

from flask_restx import Resource

from Api.api import api, conn
from Api.resources.helpers import resolve_project_config
from Access.is_auth import with_token, require_scope, audit_event

tokens_v2_ns = api.namespace("auth/tokens/v2", description="Scoped token management")

service_parser = api.parser()
service_parser.add_argument("service_name", type=str, required=True, location="json")
service_parser.add_argument("project", type=str, required=False, location="json")
service_parser.add_argument("config", type=str, required=False, location="json")
service_parser.add_argument("actions", type=list, required=True, location="json")
service_parser.add_argument("ttl_seconds", type=int, required=False, default=3600, location="json")

personal_parser = api.parser()
personal_parser.add_argument("actions", type=list, required=False, location="json")
personal_parser.add_argument("project", type=str, required=False, location="json")
personal_parser.add_argument("config", type=str, required=False, location="json")
personal_parser.add_argument("ttl_seconds", type=int, required=False, default=86400, location="json")

revoke_parser = api.parser()
revoke_parser.add_argument("token", type=str, required=True, location="json")


def _scope_from_request(project_slug, config_slug, actions):
    if not project_slug:
        return [{"actions": actions}]
    project, config = resolve_project_config(project_slug, config_slug)
    scope = {"project_id": str(project["_id"]), "actions": actions}
    if config:
        scope["config_id"] = str(config["_id"])
    return [scope]


@tokens_v2_ns.route("/service")
class ServiceTokenResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=service_parser)
    @with_token
    def post(self):
        require_scope("tokens:manage")
        args = service_parser.parse_args()
        scopes = _scope_from_request(args.get("project"), args.get("config"), args["actions"])
        expires_at = datetime.utcnow() + timedelta(seconds=args["ttl_seconds"])
        result = conn.tokens.create_token(
            token_type="service",
            created_by="system",
            subject_service_name=args["service_name"],
            scopes=scopes,
            expires_at=expires_at,
        )
        audit_event("tokens.create", status_code=201)
        return result, 201


@tokens_v2_ns.route("/personal")
class PersonalTokenResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=personal_parser)
    @with_token
    def post(self):
        require_scope("tokens:manage")
        args = personal_parser.parse_args()
        scopes = _scope_from_request(args.get("project"), args.get("config"), args.get("actions") or [])
        expires_at = datetime.utcnow() + timedelta(seconds=args["ttl_seconds"])
        result = conn.tokens.create_token(
            token_type="personal",
            created_by="system",
            subject_user="managed-user",
            scopes=scopes,
            expires_at=expires_at,
        )
        audit_event("tokens.create", status_code=201)
        return result, 201


@tokens_v2_ns.route("/revoke")
class RevokeTokenResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=revoke_parser)
    @with_token
    def post(self):
        require_scope("tokens:manage")
        args = revoke_parser.parse_args()
        result, code = conn.tokens.revoke(args["token"])
        audit_event("tokens.revoke", status_code=code)
        if code >= 400:
            api.abort(code, result.get("status"))
        return result, code
