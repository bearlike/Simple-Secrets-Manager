#!/usr/bin/env python3
from datetime import datetime, timezone

from Engines.common import is_valid_slug
from Engines.rbac import WORKSPACE_ROLES, PROJECT_ROLES, WORKSPACE_DEFAULT_SETTINGS

DEFAULT_WORKSPACE_SLUG = "default"
DEFAULT_WORKSPACE_NAME = "Default Workspace"


class Workspaces:
    def __init__(self, workspaces_col):
        self._workspaces = workspaces_col
        self._workspaces.create_index("slug", unique=True)

    @staticmethod
    def _normalize_settings(settings):
        merged = dict(WORKSPACE_DEFAULT_SETTINGS)
        if isinstance(settings, dict):
            for key in WORKSPACE_DEFAULT_SETTINGS:
                if key in settings:
                    merged[key] = settings[key]
        return merged

    def ensure_default(self):
        existing = self._workspaces.find_one({"slug": DEFAULT_WORKSPACE_SLUG})
        if existing:
            return existing
        payload = {
            "slug": DEFAULT_WORKSPACE_SLUG,
            "name": DEFAULT_WORKSPACE_NAME,
            "settings": dict(WORKSPACE_DEFAULT_SETTINGS),
            "created_at": datetime.now(timezone.utc),
        }
        try:
            self._workspaces.insert_one(payload)
        except Exception:
            pass
        return self._workspaces.find_one({"slug": DEFAULT_WORKSPACE_SLUG})

    def get_default(self):
        return self.ensure_default()

    def get_by_id(self, workspace_id):
        return self._workspaces.find_one({"_id": workspace_id})

    def get_by_slug(self, slug):
        return self._workspaces.find_one({"slug": slug})

    def get_settings(self, workspace_id):
        workspace = self.get_by_id(workspace_id)
        if not workspace:
            return None
        return self._normalize_settings(workspace.get("settings"))

    def update_settings(self, workspace_id, updates):
        workspace = self.get_by_id(workspace_id)
        if not workspace:
            return None, "Workspace not found", 404

        if not isinstance(updates, dict):
            return None, "Invalid settings payload", 400

        settings = self._normalize_settings(workspace.get("settings"))
        for key, value in updates.items():
            if key == "defaultWorkspaceRole":
                if value not in WORKSPACE_ROLES:
                    return None, "Invalid defaultWorkspaceRole", 400
                settings[key] = value
            elif key == "defaultProjectRole":
                if value not in PROJECT_ROLES:
                    return None, "Invalid defaultProjectRole", 400
                settings[key] = value
            elif key == "referencingEnabled":
                if not isinstance(value, bool):
                    return None, "referencingEnabled must be boolean", 400
                settings[key] = value
            else:
                return None, f"Unknown setting: {key}", 400

        self._workspaces.update_one(
            {"_id": workspace_id},
            {"$set": {"settings": settings, "updated_at": datetime.now(timezone.utc)}},
        )
        return settings, "OK", 200

    def create(self, slug, name):
        if not is_valid_slug(slug):
            return None, "Invalid workspace slug", 400
        payload = {
            "slug": slug,
            "name": name or slug,
            "settings": dict(WORKSPACE_DEFAULT_SETTINGS),
            "created_at": datetime.now(timezone.utc),
        }
        try:
            self._workspaces.insert_one(payload)
        except Exception:
            return None, "Workspace already exists", 400
        return payload, "OK", 201
