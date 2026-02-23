#!/usr/bin/env python3
from flask import Response, g
from flask_restx import Resource

from Api.api import api, conn
from Api.resources.helpers import resolve_project_config
from Access.is_auth import with_token, require_scope, audit_event

secrets_ns = api.namespace(
    "projects/<string:project_slug>/configs/<string:config_slug>/secrets",
    description="Config scoped secrets",
)
secret_parser = api.parser()
secret_parser.add_argument("value", type=str, required=True, location="json")
export_parser = api.parser()
export_parser.add_argument("format", type=str, choices=("json", "env"), default="json", location="args")
export_parser.add_argument("include_parent", type=bool, default=True, location="args")
export_parser.add_argument("include_meta", type=bool, default=True, location="args")


@secrets_ns.route("/<string:key>")
class SecretItemResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=secret_parser)
    @with_token
    def put(self, project_slug, config_slug, key):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope("secrets:write", project_id=project["_id"], config_id=config["_id"])
        args = secret_parser.parse_args()
        result, code = conn.secrets_v2.put(config["_id"], key, args["value"], g.actor.get("id"))
        audit_event("secrets.write", project_slug=project_slug, config_slug=config_slug, key=key, status_code=code)
        if code >= 400:
            api.abort(code, result)
        return result, code

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self, project_slug, config_slug, key):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope("secrets:read", project_id=project["_id"], config_id=config["_id"])
        result, code = conn.secrets_v2.get(config["_id"], key)
        audit_event("secrets.read", project_slug=project_slug, config_slug=config_slug, key=key, status_code=code)
        if code >= 400:
            api.abort(code, result)
        return result, code

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def delete(self, project_slug, config_slug, key):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope("secrets:write", project_id=project["_id"], config_id=config["_id"])
        result, code = conn.secrets_v2.delete(config["_id"], key)
        audit_event("secrets.write", project_slug=project_slug, config_slug=config_slug, key=key, status_code=code)
        if code >= 400:
            api.abort(code, result)
        return result, code


@secrets_ns.route("")
class SecretExportResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=export_parser)
    @with_token
    def get(self, project_slug, config_slug):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope("secrets:export", project_id=project["_id"], config_id=config["_id"])
        args = export_parser.parse_args()
        data, meta, msg, code = conn.secrets_v2.export_config(
            config["_id"],
            include_parent=args["include_parent"],
            include_metadata=args["include_meta"],
        )
        if code >= 400:
            api.abort(code, msg)
        audit_event(
            "secrets.export",
            project_slug=project_slug,
            config_slug=config_slug,
            number_of_keys=len(data.keys()),
            status_code=200,
        )
        if args["format"] == "env":
            env_blob, env_msg, env_code = conn.secrets_v2.to_env(data)
            if env_code >= 400:
                api.abort(env_code, env_msg)
            return Response(env_blob, status=200, content_type="text/plain")
        response = {"data": data, "status": "OK"}
        if args["include_meta"]:
            response["meta"] = meta
        return response, 200
