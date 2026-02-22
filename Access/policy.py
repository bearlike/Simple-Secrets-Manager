#!/usr/bin/env python3
"""Scope based authorization checks."""


def authorize(actor, action, project_id=None, config_id=None):
    if not actor:
        return False
    if actor.get("type") == "userpass":
        return True
    scopes = actor.get("scopes") or []
    for scope in scopes:
        actions = scope.get("actions") or []
        if action not in actions:
            continue
        scope_project = str(scope.get("project_id")) if scope.get("project_id") else None
        scope_config = str(scope.get("config_id")) if scope.get("config_id") else None
        req_project = str(project_id) if project_id else None
        req_config = str(config_id) if config_id else None
        if scope_config:
            if req_config and req_config == scope_config:
                return True
            continue
        if scope_project:
            if req_project and req_project == scope_project:
                return True
            continue
        if not req_project and not req_config:
            return True
    return False
