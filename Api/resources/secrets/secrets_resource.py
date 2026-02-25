#!/usr/bin/env python3
from flask import Response, g
from flask_restx import Resource

from Api.api import api, conn
from Api.resources.helpers import resolve_project_config
from Api.resources.secrets.references import SecretReferenceError, SecretReferenceResolver
from Access.is_auth import with_token, require_scope, audit_event

secrets_ns = api.namespace(
    "projects/<string:project_slug>/configs/<string:config_slug>/secrets",
    description="Config scoped secrets",
)
secret_parser = api.parser()
secret_parser.add_argument("value", type=str, required=True, location="json")
secret_get_parser = api.parser()
secret_get_parser.add_argument("raw", type=bool, default=False, location="args")
secret_get_parser.add_argument("resolve_references", type=bool, default=False, location="args")
secret_get_parser.add_argument("placeholder_max_depth", type=int, default=8, location="args")
export_parser = api.parser()
export_parser.add_argument("format", type=str, choices=("json", "env"), default="json", location="args")
export_parser.add_argument("include_parent", type=bool, default=True, location="args")
export_parser.add_argument("include_meta", type=bool, default=True, location="args")
export_parser.add_argument("raw", type=bool, default=False, location="args")
export_parser.add_argument("resolve_references", type=bool, default=False, location="args")
export_parser.add_argument("placeholder_max_depth", type=int, default=8, location="args")


def _resolve_reference_map(
    *,
    project_slug: str,
    config_slug: str,
    data: dict[str, str],
    enabled: bool,
    max_depth: int,
) -> dict[str, str]:
    if not enabled:
        return data
    resolver = SecretReferenceResolver(
        project_slug=project_slug,
        config_slug=config_slug,
        get_project_by_slug=conn.projects.get_by_slug,
        get_config_by_slug=conn.configs.get_by_slug,
        export_config=lambda cfg_id: conn.secrets_v2.export_config(
            cfg_id,
            include_parent=True,
            include_metadata=False,
        ),
        require_scope=require_scope,
        max_depth=max_depth,
    )
    return resolver.resolve_map(data)


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

    @api.doc(security=["Bearer", "Token"], parser=secret_get_parser)
    @with_token
    def get(self, project_slug, config_slug, key):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope("secrets:read", project_id=project["_id"], config_id=config["_id"])
        args = secret_get_parser.parse_args()
        resolve_references = bool(args["resolve_references"]) and not bool(args["raw"])

        result, code = conn.secrets_v2.get(config["_id"], key)
        if code >= 400:
            audit_event("secrets.read", project_slug=project_slug, config_slug=config_slug, key=key, status_code=code)
            api.abort(code, result)
        if resolve_references:
            exported, _, msg, export_code = conn.secrets_v2.export_config(
                config["_id"],
                include_parent=True,
                include_metadata=False,
            )
            if export_code >= 400 or exported is None:
                audit_event(
                    "secrets.read",
                    project_slug=project_slug,
                    config_slug=config_slug,
                    key=key,
                    status_code=export_code,
                )
                api.abort(export_code, msg)
            try:
                resolved = _resolve_reference_map(
                    project_slug=project_slug,
                    config_slug=config_slug,
                    data=exported,
                    enabled=True,
                    max_depth=args["placeholder_max_depth"],
                )
            except SecretReferenceError as exc:
                audit_event(
                    "secrets.read",
                    project_slug=project_slug,
                    config_slug=config_slug,
                    key=key,
                    status_code=exc.status_code,
                )
                api.abort(exc.status_code, exc.message)
            if key in resolved:
                result = {"key": key, "value": resolved[key], "status": "OK"}
        audit_event("secrets.read", project_slug=project_slug, config_slug=config_slug, key=key, status_code=200)
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
        resolve_references = bool(args["resolve_references"]) and not bool(args["raw"])
        data, meta, msg, code = conn.secrets_v2.export_config(
            config["_id"],
            include_parent=args["include_parent"],
            include_metadata=args["include_meta"],
        )
        if code >= 400:
            api.abort(code, msg)
        try:
            data = _resolve_reference_map(
                project_slug=project_slug,
                config_slug=config_slug,
                data=data,
                enabled=resolve_references,
                max_depth=args["placeholder_max_depth"],
            )
        except SecretReferenceError as exc:
            api.abort(exc.status_code, exc.message)
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
