#!/usr/bin/env python3
from Api.api import api, conn


def resolve_project_config(project_slug, config_slug=None):
    project = conn.projects.get_by_slug(project_slug)
    if not project:
        api.abort(404, "Project not found")
    if config_slug is None:
        return project, None
    config = conn.configs.get_by_slug(project["_id"], config_slug)
    if not config:
        api.abort(404, "Config not found")
    return project, config
