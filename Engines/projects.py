#!/usr/bin/env python3
from datetime import datetime, timezone

from bson import ObjectId

from Api.serialization import to_iso
from Engines.common import is_valid_slug


class Projects:
    def __init__(self, projects_col, workspaces_engine=None):
        self._projects = projects_col
        self._workspaces = workspaces_engine
        self._projects.create_index("slug", unique=True)
        self._projects.create_index("workspace_id")

    def _default_workspace_id(self):
        if self._workspaces is None:
            return None
        workspace = self._workspaces.ensure_default()
        return workspace.get("_id") if workspace else None

    def create(self, slug, name):
        if not is_valid_slug(slug):
            return "Invalid project slug", 400
        workspace_id = self._default_workspace_id()
        payload = {
            "slug": slug,
            "name": name or slug,
            "workspace_id": workspace_id,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            self._projects.insert_one(payload)
        except Exception:
            return "Project already exists", 400
        return payload, 201

    def get_by_id(self, project_id):
        try:
            lookup_id = ObjectId(project_id)
        except Exception:
            lookup_id = project_id
        return self._projects.find_one({"_id": lookup_id})

    def get_by_slug(self, slug):
        return self._projects.find_one({"slug": slug})

    def list_docs(self, workspace_id=None):
        query = {}
        if workspace_id is not None:
            query["$or"] = [{"workspace_id": workspace_id}, {"workspace_id": {"$exists": False}}]
        return list(self._projects.find(query).sort("slug", 1))

    def list_by_ids(self, project_ids):
        if not project_ids:
            return []
        normalized_ids = []
        for value in project_ids:
            try:
                normalized_ids.append(ObjectId(value))
            except Exception:
                normalized_ids.append(value)
        return list(self._projects.find({"_id": {"$in": normalized_ids}}).sort("slug", 1))

    def list(self, workspace_id=None, project_ids=None):
        if project_ids is not None:
            docs = self.list_by_ids(project_ids)
            if workspace_id is not None:
                docs = [doc for doc in docs if doc.get("workspace_id") in (None, workspace_id)]
        else:
            docs = self.list_docs(workspace_id=workspace_id)

        for doc in docs:
            doc["created_at"] = to_iso(doc.get("created_at"))
        return [
            {
                "slug": doc.get("slug"),
                "name": doc.get("name") or doc.get("slug"),
                "created_at": doc.get("created_at"),
            }
            for doc in docs
        ]
