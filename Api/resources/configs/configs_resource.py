#!/usr/bin/env python3
from flask_restx import Resource

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
