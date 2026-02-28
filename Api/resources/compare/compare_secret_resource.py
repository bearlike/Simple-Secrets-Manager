#!/usr/bin/env python3
from flask import g
from flask_restx import Resource, inputs

from Api.core import api, conn
from Api.resources.helpers import resolve_project_config
from Api.resources.secrets.references import (
    SecretReferenceError,
    SecretReferenceResolver,
)
from Access.is_auth import with_token
from Access.policy import authorize
from Engines.common import is_valid_env_key
from Engines.compare_issues import (
    ISSUE_BROKEN_REFERENCE_UNRESOLVED,
    ISSUE_MISSING_EFFECTIVE_VALUE,
    build_issue,
    build_issue_summary,
    classify_reference_error,
    has_broken_reference,
)

compare_ns = api.namespace(
    "projects/<string:project_slug>/compare",
    description="Project secret comparison",
)
compare_secret_parser = api.parser()
compare_secret_parser.add_argument(
    "include_parent", type=inputs.boolean, default=True, location="args"
)
compare_secret_parser.add_argument(
    "include_meta", type=inputs.boolean, default=True, location="args"
)
compare_secret_parser.add_argument(
    "include_empty", type=inputs.boolean, default=True, location="args"
)
compare_secret_parser.add_argument(
    "raw", type=inputs.boolean, default=False, location="args"
)
compare_secret_parser.add_argument(
    "resolve_references", type=inputs.boolean, default=True, location="args"
)
compare_secret_parser.add_argument(
    "limit_configs", type=int, default=200, location="args"
)
compare_secret_parser.add_argument(
    "placeholder_max_depth", type=int, default=8, location="args"
)


def _require_reference_scope(actor):
    def _check(action, project_id, config_id):
        if authorize(
            actor, action, project_id=project_id, config_id=config_id
        ):
            return None
        raise SecretReferenceError(
            "Unresolved reference due to missing access scope", status_code=403
        )

    return _check


def _build_compare_reference_resolver(
    actor, project_slug, config_slug, max_depth, root_data
):
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
        require_scope=_require_reference_scope(actor),
        max_depth=max_depth,
        root_data=root_data,
    )


def _parse_compare_args():
    args = compare_secret_parser.parse_args()
    limit_configs = args["limit_configs"]
    if limit_configs < 1:
        api.abort(400, "limit_configs must be >= 1")
    if limit_configs > 500:
        api.abort(400, "limit_configs must be <= 500")
    return args, limit_configs


def _authorized_configs_for_actor(
    actor, project_id, all_configs, limit_configs
):
    authorized = []
    for cfg in all_configs:
        if authorize(
            actor,
            "secrets:export",
            project_id=project_id,
            config_id=cfg.get("_id"),
        ):
            authorized.append(cfg)
        if len(authorized) >= limit_configs:
            break
    return authorized


def _load_exported_config(config_id, include_parent, exported_cache):
    if config_id not in exported_cache:
        exported, _, export_msg, export_code = conn.secrets_v2.export_config(
            config_id,
            include_parent=include_parent,
            include_metadata=False,
        )
        exported_cache[config_id] = (exported, export_msg, export_code)
    return exported_cache[config_id]


def _row_value_issues(effective):
    value = effective.get("value")
    if value is None:
        return (
            value,
            [
                build_issue(
                    ISSUE_MISSING_EFFECTIVE_VALUE,
                    "Key is missing in this config and its inheritance chain.",
                )
            ],
            True,
        )
    if not isinstance(value, str) or "${" not in value:
        return value, [], True
    return value, [], False


def _collect_validation_issues(resolver, key, value):
    issues = []
    seen_codes = set()
    for error_message in resolver.validate_value_references(
        key=key, value=value
    ):
        code_for_error = classify_reference_error(error_message)
        if code_for_error in seen_codes:
            continue
        seen_codes.add(code_for_error)
        issues.append(build_issue(code_for_error, error_message))
    return issues, seen_codes


def _resolve_value_if_allowed(
    *,
    resolve_references,
    issues,
    resolver,
    exported,
    effective,
    key,
    seen_codes,
):
    if not resolve_references or has_broken_reference(issues):
        return
    try:
        resolved = resolver.resolve_map(exported)
    except SecretReferenceError as exc:
        code_for_error = classify_reference_error(exc.message)
        if code_for_error not in seen_codes:
            issues.append(build_issue(code_for_error, exc.message))
    else:
        effective["value"] = resolved.get(key)


def _annotate_row_issues(
    row,
    *,
    actor,
    project_slug,
    key,
    args,
    resolve_references,
    config_id_by_slug,
    exported_cache,
):
    effective = row.get("effective", {})
    value, issues, done = _row_value_issues(effective)
    if done:
        return issues

    config_id = config_id_by_slug.get(row.get("configSlug"))
    if config_id is None:
        issues.append(
            build_issue(
                ISSUE_BROKEN_REFERENCE_UNRESOLVED,
                "Unable to validate references for this config.",
            )
        )
        return issues

    exported, export_msg, export_code = _load_exported_config(
        config_id,
        include_parent=args["include_parent"],
        exported_cache=exported_cache,
    )
    if export_code >= 400 or exported is None:
        issues.append(
            build_issue(
                ISSUE_BROKEN_REFERENCE_UNRESOLVED,
                f"Unable to evaluate references: {export_msg}",
            )
        )
        return issues

    resolver = _build_compare_reference_resolver(
        actor=actor,
        project_slug=project_slug,
        config_slug=row.get("configSlug"),
        max_depth=args["placeholder_max_depth"],
        root_data=exported,
    )
    validation_issues, seen_codes = _collect_validation_issues(
        resolver, key, value
    )
    issues.extend(validation_issues)
    _resolve_value_if_allowed(
        resolve_references=resolve_references,
        issues=issues,
        resolver=resolver,
        exported=exported,
        effective=effective,
        key=key,
        seen_codes=seen_codes,
    )
    return issues


def _annotate_rows(
    rows,
    *,
    actor,
    project_slug,
    key,
    args,
    resolve_references,
    config_id_by_slug,
):
    exported_cache = {}
    for row in rows:
        issues = _annotate_row_issues(
            row,
            actor=actor,
            project_slug=project_slug,
            key=key,
            args=args,
            resolve_references=resolve_references,
            config_id_by_slug=config_id_by_slug,
            exported_cache=exported_cache,
        )
        row["issues"] = issues
        row["hasIssues"] = len(issues) > 0


@compare_ns.route("/secrets/<string:key>")
class CompareSecretResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=compare_secret_parser)
    @with_token
    def get(self, project_slug, key):
        if not is_valid_env_key(key):
            api.abort(400, "Invalid secret key")

        args, limit_configs = _parse_compare_args()
        project, _ = resolve_project_config(project_slug)
        all_configs = conn.configs.list_raw(project["_id"])
        actor = g.actor
        authorized_configs = _authorized_configs_for_actor(
            actor,
            project_id=project["_id"],
            all_configs=all_configs,
            limit_configs=limit_configs,
        )

        rows, msg, code = conn.secrets_v2.compare_key_across_configs(
            authorized_configs,
            key,
            include_parent=args["include_parent"],
            include_metadata=args["include_meta"],
            include_empty=args["include_empty"],
        )
        if code >= 400:
            api.abort(code, msg)

        resolve_references = bool(args["resolve_references"]) and not bool(
            args["raw"]
        )
        config_id_by_slug = {
            cfg["slug"]: cfg["_id"]
            for cfg in authorized_configs
            if "slug" in cfg and "_id" in cfg
        }
        _annotate_rows(
            rows,
            actor=actor,
            project_slug=project_slug,
            key=key,
            args=args,
            resolve_references=resolve_references,
            config_id_by_slug=config_id_by_slug,
        )

        response_configs = []
        unique_effective_values = set()
        missing_count = 0
        for row in rows:
            value = row.get("effective", {}).get("value")
            if value is None:
                missing_count += 1
            else:
                unique_effective_values.add(value)
            response_configs.append(
                {k: v for k, v in row.items() if k != "configId"}
            )

        return {
            "status": "OK",
            "project": project_slug,
            "key": key,
            "configs": response_configs,
            "summary": {
                "uniqueEffectiveValues": len(unique_effective_values),
                "missingCount": missing_count,
                "conflict": len(unique_effective_values) > 1,
            },
            "issuesSummary": build_issue_summary(response_configs),
        }, 200
