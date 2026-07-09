#!/usr/bin/env python3
from flask_restx import Resource
from flask import g

from Api.core import api, conn
from Api.resources.helpers import resolve_project_config
from Access.is_auth import with_token, require_scope

configs_ns = api.namespace(
    "projects/<string:project_slug>/configs", description="Config management"
)
config_create_parser = api.parser()
config_create_parser.add_argument(
    "slug", type=str, required=True, location="json"
)
config_create_parser.add_argument(
    "name", type=str, required=False, location="json"
)
config_create_parser.add_argument(
    "parent", type=str, required=False, location="json"
)
config_update_parser = api.parser()
config_update_parser.add_argument(
    "name", type=str, required=False, location="json", store_missing=False
)
config_update_parser.add_argument(
    "parent", type=str, required=False, location="json", store_missing=False
)


def _config_audit_event(action, project_slug, config_slug, method, path):
    return {
        "actor_type": "token",
        "actor_id": g.actor.get("id"),
        "token_id": g.actor.get("token_id"),
        "action": action,
        "project_slug": project_slug,
        "config_slug": config_slug,
        "method": method,
        "path": path,
        "status_code": 200,
        "latency_ms": 0,
    }


@configs_ns.route("")
class ConfigsResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self, project_slug):
        project, _ = resolve_project_config(project_slug)
        require_scope("configs:read", project_id=project["_id"])
        return {"configs": conn.configs.list(project["_id"])}

    @api.doc(security=["Bearer", "Token"], parser=config_create_parser)
    @with_token
    def post(self, project_slug):
        project, _ = resolve_project_config(project_slug)
        require_scope("configs:write", project_id=project["_id"])
        args = config_create_parser.parse_args()
        parent_id = None
        if args.get("parent"):
            _, parent_cfg = resolve_project_config(
                project_slug, args["parent"]
            )
            parent_id = parent_cfg["_id"]
        result, code = conn.configs.create(
            project["_id"], args["slug"], args.get("name"), parent_id
        )
        if code >= 400:
            api.abort(code, result)
        return {
            "status": "OK",
            "config": {"slug": result["slug"], "name": result["name"]},
        }, 201


@configs_ns.route("/<string:config_slug>")
class ConfigItemResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=config_update_parser)
    @with_token
    def patch(self, project_slug, config_slug):
        project, _ = resolve_project_config(project_slug, config_slug)
        require_scope("configs:write", project_id=project["_id"])
        args = config_update_parser.parse_args()

        parent_provided = "parent" in args
        parent_config_id = None
        if parent_provided:
            parent_value = args.get("parent")
            if parent_value:
                parent_cfg = conn.configs.get_by_slug(
                    project["_id"], parent_value
                )
                if not parent_cfg:
                    api.abort(404, "Parent config not found")
                parent_config_id = parent_cfg["_id"]

        result, code = conn.configs.update(
            project["_id"],
            config_slug,
            name=args.get("name"),
            parent_config_id=parent_config_id,
            parent_provided=parent_provided,
        )
        if code >= 400:
            api.abort(code, result)
        conn.audit.write_event(
            _config_audit_event(
                "configs.write",
                project_slug,
                config_slug,
                "PATCH",
                f"/api/projects/{project_slug}/configs/{config_slug}",
            )
        )
        return {
            "status": "OK",
            "config": {
                "slug": result.get("slug"),
                "name": result.get("name"),
            },
        }, 200

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def delete(self, project_slug, config_slug):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope("configs:write", project_id=project["_id"])
        result, code = conn.configs.delete(project["_id"], config_slug)
        if code >= 400:
            api.abort(code, result)
        conn.secrets_v2.delete_by_config(config["_id"])
        conn.secrets_v2.recompute_project_icon_slugs(project["_id"])
        conn.audit.write_event(
            _config_audit_event(
                "configs.delete",
                project_slug,
                config_slug,
                "DELETE",
                f"/api/projects/{project_slug}/configs/{config_slug}",
            )
        )
        return {"status": "OK"}, 200
