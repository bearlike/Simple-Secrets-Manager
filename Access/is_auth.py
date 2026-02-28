#!/usr/bin/env python3
from functools import wraps
from time import perf_counter

from flask import g, request
from flask_httpauth import HTTPBasicAuth

from Api.api import conn, api
from Access.policy import authorize

userpass: HTTPBasicAuth = HTTPBasicAuth()


def _extract_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip()
    return request.headers.get("X-API-KEY", type=str, default=None)


def _audit_request(event):
    event.update(
        {
            "method": request.method,
            "path": request.path,
            "ip": request.remote_addr,
            "user_agent": request.user_agent.string,
            "status_code": event.get("status_code", 200),
            "latency_ms": int((perf_counter() - g.get("request_started", perf_counter())) * 1000),
        }
    )
    conn.audit.write_event(event)


def require_token():
    token_to_check = _extract_token()
    if not token_to_check:
        api.abort(401, "Missing API token")
    actor, err = conn.tokens.authenticate(token_to_check)
    if err:
        _audit_request(
            {
                "actor_type": "token",
                "actor_id": None,
                "token_id": None,
                "action": "auth.fail",
                "status_code": 401,
                "reason": err,
            }
        )
        api.abort(401, f"Not Authorized to access the requested resource ({err})")
    g.actor = actor
    return actor


def require_scope(action, project_id=None, config_id=None):
    actor = getattr(g, "actor", None) or require_token()
    if not authorize(actor, action, project_id=project_id, config_id=config_id):
        api.abort(403, f"Missing scope: {action}")
    return actor


def audit_event(action, **kwargs):
    actor = getattr(g, "actor", None) or {}
    _audit_request(
        {
            "actor_type": "token" if actor.get("type") == "token" else "user",
            "actor_id": actor.get("subject_user") or actor.get("subject_service_name") or actor.get("id"),
            "token_id": actor.get("token_id"),
            "action": action,
            **kwargs,
        }
    )


@userpass.verify_password
def verify_userpass(username, password):
    if conn.userpass.is_authorized(username, password):
        g.actor = {"type": "userpass", "subject_user": username, "id": username}
        return username
    api.abort(401, "Not Authorized to access the requested resource")
    return None


def with_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        g.request_started = perf_counter()
        require_token()
        return fn(*args, **kwargs)

    return wrapper
