#!/usr/bin/env python3
"""Scope based authorization checks."""


def _has_scope(scopes, action, project_id=None, config_id=None):
    for scope in scopes or []:
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
        return True
    return False


def authorize(actor, action, project_id=None, config_id=None):
    if not actor:
        return False
    if not _has_scope(actor.get("scopes"), action, project_id=project_id, config_id=config_id):
        return False
    token_scopes = actor.get("token_scopes")
    if token_scopes is None:
        return True
    return _has_scope(token_scopes, action, project_id=project_id, config_id=config_id)
