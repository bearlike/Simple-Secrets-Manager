#!/usr/bin/env python3
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from ssm_server.api.serialization import to_iso
from ssm_server.engines.common import is_valid_slug


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

    def create(self, slug, name, description=None):
        if not is_valid_slug(slug):
            return "Invalid project slug", 400
        workspace_id = self._default_workspace_id()
        payload = {
            "slug": slug,
            "name": name or slug,
            "workspace_id": workspace_id,
            "archived": False,
            "description": (str(description).strip() or None)
            if description is not None
            else None,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            self._projects.insert_one(payload)
        except DuplicateKeyError:
            return "Project already exists", 400
        return payload, 201

    def update(self, slug, name=None, archived=None, description=None):
        set_dict = {}
        if name is not None:
            if not str(name).strip():
                return "Project name is required", 400
            set_dict["name"] = str(name).strip()
        if archived is not None:
            if not isinstance(archived, bool):
                return "archived must be boolean", 400
            set_dict["archived"] = archived
        # None leaves the description untouched; "" clears it.
        if description is not None:
            set_dict["description"] = str(description).strip() or None
        if not set_dict:
            return "No fields to update", 400
        result = self._projects.update_one({"slug": slug}, {"$set": set_dict})
        if result.matched_count == 0:
            return "Project not found", 404
        return self._projects.find_one({"slug": slug}), 200

    def delete(self, slug):
        doc = self._projects.find_one({"slug": slug})
        if not doc:
            return "Project not found", 404
        self._projects.delete_one({"_id": doc["_id"]})
        return doc, 200

    def get_by_id(self, project_id):
        try:
            lookup_id = ObjectId(project_id)
        except (InvalidId, TypeError, ValueError):
            lookup_id = project_id
        return self._projects.find_one({"_id": lookup_id})

    def get_by_slug(self, slug):
        return self._projects.find_one({"slug": slug})

    def list_docs(self, workspace_id=None):
        query = {}
        if workspace_id is not None:
            query["$or"] = [
                {"workspace_id": workspace_id},
                {"workspace_id": {"$exists": False}},
            ]
        return list(self._projects.find(query).sort("slug", 1))

    def list_by_ids(self, project_ids):
        if not project_ids:
            return []
        normalized_ids = []
        for value in project_ids:
            try:
                normalized_ids.append(ObjectId(value))
            except (InvalidId, TypeError, ValueError):
                normalized_ids.append(value)
        return list(
            self._projects.find({"_id": {"$in": normalized_ids}}).sort(
                "slug", 1
            )
        )

    def list(self, workspace_id=None, project_ids=None, archived=False):
        if project_ids is not None:
            docs = self.list_by_ids(project_ids)
            if workspace_id is not None:
                docs = [
                    doc
                    for doc in docs
                    if doc.get("workspace_id") in (None, workspace_id)
                ]
        else:
            docs = self.list_docs(workspace_id=workspace_id)

        # Filter in Python: list_docs/list_by_ids build the DB query and stay
        # archive-agnostic (the RBAC path depends on them), so the split lives
        # here. Legacy docs without the field count as active (archived is not
        # True); archived=True keeps only archived.
        if archived:
            docs = [doc for doc in docs if doc.get("archived") is True]
        else:
            docs = [doc for doc in docs if doc.get("archived") is not True]

        for doc in docs:
            doc["created_at"] = to_iso(doc.get("created_at"))
        return [
            {
                "slug": doc.get("slug"),
                "name": doc.get("name") or doc.get("slug"),
                "description": doc.get("description"),
                # camelCase `createdAt` is the canonical API form; snake_case
                # `created_at` is dual-emitted for back-compat and deprecated
                # for removal in the next major.
                "createdAt": doc.get("created_at"),
                "created_at": doc.get("created_at"),
                "archived": bool(doc.get("archived", False)),
            }
            for doc in docs
        ]
