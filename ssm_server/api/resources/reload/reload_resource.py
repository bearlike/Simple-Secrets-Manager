#!/usr/bin/env python3
from flask import request
from flask_restx import Resource
from pydantic import ValidationError

from ssm_contracts import ReloadReport, summarize_validation_error
from ssm_telemetry import emit_event
from ssm_server.api.core import api, conn
from ssm_server.api.resources.helpers import resolve_project_config
from ssm_server.api.serialization import oid_to_str
from ssm_server.engines.reload_status import group_status
from ssm_server.access.is_auth import with_token, require_scope, audit_event

reload_ns = api.namespace("reload", description="Secrets reload reporting")
reload_parser = api.parser()
reload_parser.add_argument("project", type=str, required=True, location="json")
reload_parser.add_argument("config", type=str, required=True, location="json")
reload_parser.add_argument(
    "container", type=str, required=False, location="json"
)
reload_parser.add_argument("host", type=str, required=False, location="json")
reload_parser.add_argument(
    "from_revision", type=str, required=False, location="json"
)
reload_parser.add_argument(
    "to_revision", type=str, required=False, location="json"
)

status_parser = api.parser()
status_parser.add_argument(
    "project", type=str, required=False, location="args"
)
status_parser.add_argument("config", type=str, required=False, location="args")


def _optional_string(value):
    """Coerce an optional field to ``str`` or ``None`` for the audit log."""
    return value if isinstance(value, str) else None


@reload_ns.route("/events")
class ReloadEventsResource(Resource):
    @api.doc(security=["Bearer", "Token"], parser=reload_parser)
    @with_token
    def post(self):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            api.abort(400, "Request body must be a JSON object")
        project_slug = payload.get("project")
        config_slug = payload.get("config")
        if not isinstance(project_slug, str) or not project_slug:
            api.abort(400, "project is required")
        if not isinstance(config_slug, str) or not config_slug:
            api.abort(400, "config is required")
        project, config = resolve_project_config(project_slug, config_slug)
        require_scope(
            "reload:report",
            project_id=project["_id"],
            config_id=config["_id"],
        )
        audit_event(
            "reload.applied",
            project_slug=project_slug,
            config_slug=config_slug,
            container=_optional_string(payload.get("container")),
            host=_optional_string(payload.get("host")),
            from_revision=_optional_string(payload.get("from_revision")),
            to_revision=_optional_string(payload.get("to_revision")),
            status_code=200,
        )
        return {"status": "OK"}, 200


@reload_ns.route("/report")
class ReloadReportResource(Resource):
    """Per-cycle fleet heartbeat from a reloader (one config group/cycle).

    Deliberately writes NO audit event: the reloader posts one of these every
    poll (~30s) per config, and steady state is almost always a 304 "current"
    heartbeat — auditing each would flood the trail. The meaningful signal, an
    applied recreate, still lands in the audit log via the untouched
    ``POST /reload/events`` path. This endpoint only refreshes the fleet read
    model behind ``GET /reload/status``.
    """

    @api.doc(security=["Bearer", "Token"])
    @with_token
    def post(self):
        raw = request.get_json(silent=True)
        if not isinstance(raw, dict):
            api.abort(400, "Request body must be a JSON object")
        try:
            report = ReloadReport.model_validate(raw)
        except ValidationError as exc:
            # One readable line in the standard envelope — never the raw repr.
            api.abort(400, summarize_validation_error(exc))
        project, config = resolve_project_config(report.project, report.config)
        require_scope(
            "reload:report",
            project_id=project["_id"],
            config_id=config["_id"],
        )
        conn.reload_status.write_report(
            project_id=oid_to_str(project["_id"]),
            config_id=oid_to_str(config["_id"]),
            project_slug=report.project,
            config_slug=report.config,
            host=report.reporter.host,
            instance_id=report.reporter.instance_id,
            version=report.reporter.version,
            trigger=report.trigger,
            revision=report.revision,
            outcome=report.outcome,
            error=report.error,
            units=[unit.model_dump() for unit in report.units],
        )
        emit_event(
            "ssm_server.reload.report_accepted",
            attributes={
                "ssm.project": report.project,
                "ssm.config": report.config,
                "ssm.outcome": report.outcome,
                "ssm.trigger": report.trigger,
            },
        )
        return {"status": "OK"}, 200


@reload_ns.route("/status")
class ReloadStatusResource(Resource):
    """Admin fleet view: every reloader instance's latest per-config status.

    Read-gated on ``audit:read`` (same as the audit trail), optionally scoped
    to a project (and, with it, a config — mirroring the audit endpoint).
    """

    @api.doc(security=["Bearer", "Token"], parser=status_parser)
    @with_token
    def get(self):
        args = status_parser.parse_args()
        project_slug = args.get("project")
        config_slug = args.get("config")
        if config_slug and not project_slug:
            api.abort(
                400, "project query param is required when config is provided"
            )
        project_id = None
        config_id = None
        if project_slug:
            project, config = resolve_project_config(project_slug, config_slug)
            project_id = project["_id"]
            config_id = config["_id"] if config else None
        require_scope("audit:read", project_id=project_id, config_id=config_id)
        docs = conn.reload_status.query_status(
            project_id=oid_to_str(project_id),
            config_id=oid_to_str(config_id),
        )
        return {"status": "OK", "data": group_status(docs)}
