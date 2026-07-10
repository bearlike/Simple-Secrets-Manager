#!/usr/bin/env python3
from flask_restx import Resource

from ssm_server.api.core import api, conn
from ssm_server.api.resources.helpers import resolve_project_config
from ssm_server.access.is_auth import (
    with_token,
    require_scope,
    audit_event,
)

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
config_create_parser.add_argument(
    "description", type=str, required=False, location="json"
)
config_update_parser = api.parser()
config_update_parser.add_argument(
    "name", type=str, required=False, location="json", store_missing=False
)
config_update_parser.add_argument(
    "parent", type=str, required=False, location="json", store_missing=False
)
config_update_parser.add_argument(
    "description",
    type=str,
    required=False,
    location="json",
    store_missing=False,
)


def _referencing_config_labels(config_ids, project_slug):
    """Render referencing configs without leaking out-of-scope slugs.

    Same-project references are named ``project/config`` so the 409 is
    actionable; references from OTHER projects collapse to a count — the
    deleter's ``configs:write`` on this project proves nothing about
    visibility over those, so their slugs must not appear in the error.
    """
    labels = set()
    foreign_project_ids = set()
    for config_id in config_ids:
        cfg = conn.configs.get_by_id(config_id)
        if not cfg:
            continue
        project = conn.projects.get_by_id(cfg.get("project_id"))
        slug = project.get("slug") if project else None
        if slug == project_slug:
            labels.add(f"{slug}/{cfg.get('slug')}")
        else:
            foreign_project_ids.add(str(cfg.get("project_id")))
    parts = sorted(labels)
    if foreign_project_ids:
        count = len(foreign_project_ids)
        plural = "s" if count != 1 else ""
        parts.append(f"{count} other project{plural}")
    return parts


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
            project["_id"],
            args["slug"],
            args.get("name"),
            parent_id,
            description=args.get("description"),
        )
        if code >= 400:
            api.abort(code, result)
        return {
            "status": "OK",
            "config": {
                "slug": result["slug"],
                "name": result["name"],
                "description": result.get("description"),
            },
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
            description=args.get("description"),
        )
        if code >= 400:
            api.abort(code, result)
        audit_event(
            "configs.write",
            project_slug=project_slug,
            config_slug=config_slug,
            status_code=200,
        )
        return {
            "status": "OK",
            "config": {
                "slug": result.get("slug"),
                "name": result.get("name"),
                "description": result.get("description"),
            },
        }, 200

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def delete(self, project_slug, config_slug):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope("configs:write", project_id=project["_id"])
        # Block deletes that would leave dangling ${...} references: a config
        # removed while other secrets still point at it only fails later, at
        # read time. Mirror the child-config 409 and name the offenders.
        referencing_ids = conn.secrets_v2.find_configs_referencing(
            config["_id"],
            project_slug,
            config_slug,
            conn.configs.list_ids(project["_id"]),
        )
        if referencing_ids:
            labels = _referencing_config_labels(referencing_ids, project_slug)
            api.abort(
                409,
                "Config is referenced by secrets in "
                f"{', '.join(labels)}; update them first",
            )
        result, code = conn.configs.delete(project["_id"], config_slug)
        if code >= 400:
            api.abort(code, result)
        conn.secrets_v2.delete_by_config(config["_id"])
        conn.secrets_v2.recompute_project_icon_slugs(project["_id"])
        audit_event(
            "configs.delete",
            project_slug=project_slug,
            config_slug=config_slug,
            status_code=200,
        )
        return {"status": "OK"}, 200
