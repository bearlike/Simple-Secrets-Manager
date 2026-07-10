#!/usr/bin/env python3
from typing import Optional

from flask import Response, g, request
from flask_restx import Resource, inputs
from loguru import logger

from ssm_server.api.core import api, conn
from ssm_server.api.resources.helpers import resolve_project_config
from ssm_server.api.resources.secrets.references import (
    SecretReferenceError,
    SecretReferenceResolver,
)
from ssm_server.engines.secrets_v2 import config_export_etag
from ssm_server.access.is_auth import with_token, require_scope, audit_event


def _if_none_match_matches(header: Optional[str], etag: str) -> bool:
    """Return True when an ``If-None-Match`` header covers ``etag``."""
    if not header:
        return False
    candidate = header.strip()
    if candidate == "*":
        return True
    for token in candidate.split(","):
        token = token.strip()
        if token.startswith("W/"):
            token = token[2:].strip()
        if token == etag:
            return True
    return False


secrets_ns = api.namespace(
    "projects/<string:project_slug>/configs/<string:config_slug>/secrets",
    description="Config scoped secrets",
)
secret_parser = api.parser()
secret_parser.add_argument("value", type=str, required=True, location="json")
secret_parser.add_argument(
    "icon_slug", type=str, required=False, location="json"
)
secret_parser.add_argument(
    "description", type=str, required=False, location="json"
)
secret_parser.add_argument(
    "sensitive",
    type=inputs.boolean,
    required=False,
    location="json",
    store_missing=False,
)
secret_get_parser = api.parser()
secret_get_parser.add_argument(
    "raw", type=inputs.boolean, default=False, location="args"
)
secret_get_parser.add_argument(
    "resolve_references", type=inputs.boolean, default=False, location="args"
)
secret_get_parser.add_argument(
    "placeholder_max_depth", type=int, default=8, location="args"
)
export_parser = api.parser()
export_parser.add_argument(
    "format",
    type=str,
    choices=("json", "env"),
    default="json",
    location="args",
)
export_parser.add_argument(
    "include_parent", type=inputs.boolean, default=True, location="args"
)
export_parser.add_argument(
    "include_meta", type=inputs.boolean, default=True, location="args"
)
export_parser.add_argument(
    "raw", type=inputs.boolean, default=False, location="args"
)
export_parser.add_argument(
    "resolve_references", type=inputs.boolean, default=False, location="args"
)
export_parser.add_argument(
    "include_provenance", type=inputs.boolean, default=False, location="args"
)
export_parser.add_argument(
    "placeholder_max_depth", type=int, default=8, location="args"
)


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
    resolver = _build_reference_resolver(
        project_slug=project_slug,
        config_slug=config_slug,
        max_depth=max_depth,
        root_data=data,
    )
    return resolver.resolve_map(data)


def _build_reference_resolver(
    *,
    project_slug: str,
    config_slug: str,
    max_depth: int,
    root_data: Optional[dict[str, str]] = None,
) -> SecretReferenceResolver:
    return SecretReferenceResolver(
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
        root_data=root_data,
    )


def _provenance_env_annotations(
    project: dict, meta: Optional[dict]
) -> dict[str, str]:
    """Build ``{key: '# from <config>[: <description>]'}`` from export meta.

    Only keys whose effective value came from a resolvable ``source`` config
    are annotated; the source config's description (same project) is appended
    when present.
    """
    annotations: dict[str, str] = {}
    description_by_slug: dict[str, Optional[str]] = {}
    for key, entry in (meta or {}).items():
        source = entry.get("source")
        if not source:
            continue
        if source not in description_by_slug:
            cfg = conn.configs.get_by_slug(project["_id"], source)
            description_by_slug[source] = (
                cfg.get("description") if cfg else None
            )
        comment = f"# from {source}"
        description = description_by_slug[source]
        if description:
            comment += f": {description}"
        annotations[key] = comment
    return annotations


@secrets_ns.route("/<string:key>")
class SecretItemResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=secret_parser)
    @with_token
    def put(self, project_slug, config_slug, key):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope(
            "secrets:write", project_id=project["_id"], config_id=config["_id"]
        )
        args = secret_parser.parse_args()
        value = args["value"]
        if not isinstance(value, str):
            api.abort(400, "value must be a string")
        raw_payload = request.get_json(silent=True)
        payload = raw_payload if isinstance(raw_payload, dict) else {}
        icon_slug_provided = "icon_slug" in payload
        icon_slug = payload.get("icon_slug") if icon_slug_provided else None
        if icon_slug is not None and not isinstance(icon_slug, str):
            api.abort(400, "icon_slug must be a string or null")
        sensitive_provided = "sensitive" in payload
        sensitive = args.get("sensitive") if sensitive_provided else None
        description_provided = "description" in payload
        description = (
            payload.get("description") if description_provided else None
        )
        if description is not None and not isinstance(description, str):
            api.abort(400, "description must be a string or null")

        if "${" in value:
            exported, _, msg, code = conn.secrets_v2.export_config(
                config["_id"],
                include_parent=True,
                include_metadata=False,
            )
            if code >= 400 or exported is None:
                api.abort(code, msg)
            staged = dict(exported)
            staged[key] = value
            resolver = _build_reference_resolver(
                project_slug=project_slug,
                config_slug=config_slug,
                max_depth=8,
                root_data=staged,
            )
            try:
                errors = resolver.validate_value_references(
                    key=key, value=value
                )
            except SecretReferenceError as exc:
                api.abort(exc.status_code, exc.message)
            if errors:
                api.abort(400, "; ".join(errors))

        # Trace which fields the client actually sent -- "saved but looks
        # unchanged" reports hinge on exactly this (provided vs omitted).
        # LOG HYGIENE: metadata only. Never log `value` (or any secret
        # payload) here -- key names/slugs/flags are the allowed set.
        logger.debug(
            "secrets.put {}/{} key={} icon_provided={} icon={} "
            "sensitive_provided={} description_provided={}",
            project_slug,
            config_slug,
            key,
            icon_slug_provided,
            icon_slug,
            sensitive_provided,
            description_provided,
        )
        result, code = conn.secrets_v2.put(
            config["_id"],
            key,
            value,
            g.actor.get("id"),
            icon_slug=icon_slug,
            icon_slug_provided=icon_slug_provided,
            sensitive=sensitive,
            sensitive_provided=sensitive_provided,
            description=description,
            description_provided=description_provided,
        )
        audit_event(
            "secrets.write",
            project_slug=project_slug,
            config_slug=config_slug,
            key=key,
            status_code=code,
        )
        if code >= 400:
            api.abort(code, result)
        return result, code

    @api.doc(security=["Bearer", "Token"], parser=secret_get_parser)
    @with_token
    def get(self, project_slug, config_slug, key):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope(
            "secrets:read", project_id=project["_id"], config_id=config["_id"]
        )
        args = secret_get_parser.parse_args()
        resolve_references = bool(args["resolve_references"]) and not bool(
            args["raw"]
        )

        result, code = conn.secrets_v2.get(config["_id"], key)
        if code >= 400:
            audit_event(
                "secrets.read",
                project_slug=project_slug,
                config_slug=config_slug,
                key=key,
                status_code=code,
            )
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
        audit_event(
            "secrets.read",
            project_slug=project_slug,
            config_slug=config_slug,
            key=key,
            status_code=200,
        )
        return result, code

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def delete(self, project_slug, config_slug, key):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope(
            "secrets:delete",
            project_id=project["_id"],
            config_id=config["_id"],
        )
        result, code = conn.secrets_v2.delete(config["_id"], key)
        audit_event(
            "secrets.delete",
            project_slug=project_slug,
            config_slug=config_slug,
            key=key,
            status_code=code,
        )
        if code >= 400:
            api.abort(code, result)
        return result, code


@secrets_ns.route("")
class SecretExportResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=export_parser)
    @with_token
    def get(self, project_slug, config_slug):
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope(
            "secrets:export",
            project_id=project["_id"],
            config_id=config["_id"],
        )
        args = export_parser.parse_args()
        raw = bool(args["raw"])
        resolve_arg = bool(args["resolve_references"])
        include_provenance = bool(args["include_provenance"])
        data, meta, msg, code = conn.secrets_v2.export_config(
            config["_id"],
            include_parent=args["include_parent"],
            include_metadata=args["include_meta"],
            include_provenance=include_provenance,
        )
        if code >= 400:
            api.abort(code, msg)
        # Resolve references whenever the caller asks, independent of the
        # `raw` flag, so the ETag hashes the fully-resolved value-set and is
        # stable across format / include_meta / raw representations.
        resolved = data
        if resolve_arg:
            try:
                resolved = _resolve_reference_map(
                    project_slug=project_slug,
                    config_slug=config_slug,
                    data=data,
                    enabled=True,
                    max_depth=args["placeholder_max_depth"],
                )
            except SecretReferenceError as exc:
                if not raw:
                    api.abort(exc.status_code, exc.message)
                resolved = data
        # The ETag identifies the REPRESENTATION: when the response carries
        # per-key metadata (include_meta -- default true -- or provenance),
        # `meta` is non-None and folds into the tag, so a metadata-only edit
        # (icon slug, sensitivity, description) flips it and the console's
        # conditional refetch is served fresh instead of a stale 304 that
        # keeps rendering the pre-edit icon. Callers that want the value-only
        # tag (the reloader: its 304 divergence check must react to VALUE
        # changes alone, or icon edits would recreate containers) explicitly
        # request include_meta=false, which keeps their tag byte-identical to
        # previously stamped revisions.
        etag = config_export_etag(resolved, meta)
        # LOG HYGIENE: metadata only -- key COUNT, never key names or values.
        # The etag is safe to log: it is already exposed as a response header
        # and stored in world-readable container labels by the reloader.
        logger.debug(
            "secrets.export {}/{} etag={} include_meta={} provenance={} "
            "raw={} resolve={} keys={}",
            project_slug,
            config_slug,
            etag,
            bool(args["include_meta"]),
            include_provenance,
            raw,
            resolve_arg,
            len(resolved),
        )
        if _if_none_match_matches(request.headers.get("If-None-Match"), etag):
            # A 304 is still a scoped read of the export data; audit it too,
            # otherwise the reloader's steady-state polling (which is almost
            # always 304) would leave the secrets:export access unlogged.
            audit_event(
                "secrets.export",
                project_slug=project_slug,
                config_slug=config_slug,
                number_of_keys=len(resolved),
                status_code=304,
            )
            return "", 304, {"ETag": etag}

        body_data = data if raw else resolved
        audit_event(
            "secrets.export",
            project_slug=project_slug,
            config_slug=config_slug,
            number_of_keys=len(body_data.keys()),
            status_code=200,
        )
        if args["format"] == "env":
            annotations = (
                _provenance_env_annotations(project, meta)
                if include_provenance
                else None
            )
            env_blob, env_msg, env_code = conn.secrets_v2.to_env(
                body_data, annotations
            )
            if env_code >= 400:
                api.abort(env_code, env_msg)
            response = Response(
                env_blob, status=200, content_type="text/plain"
            )
            response.headers["ETag"] = etag
            return response
        response = {"data": body_data, "status": "OK"}
        if args["include_meta"]:
            response["meta"] = meta
        return response, 200, {"ETag": etag}
