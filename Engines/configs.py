#!/usr/bin/env python3
from datetime import datetime, timezone

from bson import ObjectId

from Api.serialization import to_iso
from Engines.common import is_valid_slug


class Configs:
    def __init__(self, configs_col):
        self._configs = configs_col
        self._configs.create_index(
            [("project_id", 1), ("slug", 1)], unique=True
        )

    def create(self, project_id, slug, name, parent_config_id=None):
        if not is_valid_slug(slug):
            return "Invalid config slug", 400
        if parent_config_id is not None and not isinstance(
            parent_config_id, ObjectId
        ):
            return "Invalid parent config id", 400
        parent = None
        if parent_config_id is not None:
            parent = self._configs.find_one({"_id": parent_config_id})
            if parent is None:
                return "Parent config not found", 404
            if parent["project_id"] != project_id:
                return "Parent config must belong to the same project", 400
        payload = {
            "project_id": project_id,
            "slug": slug,
            "name": name or slug,
            "parent_config_id": parent_config_id,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            self._configs.insert_one(payload)
        except Exception:
            return "Config already exists", 400
        return payload, 201

    def _would_create_cycle(self, config_id, new_parent_id):
        """True if reparenting ``config_id`` under ``new_parent_id`` would
        form a cycle (the new parent chain leads back to the config)."""
        seen = set()
        current = new_parent_id
        while current is not None:
            if current == config_id:
                return True
            if current in seen:
                break
            seen.add(current)
            doc = self._configs.find_one(
                {"_id": current}, {"parent_config_id": 1}
            )
            if not doc:
                break
            current = doc.get("parent_config_id")
        return False

    def _validate_new_parent(self, project_id, config, parent_config_id):
        """Return ``(error, code)`` if ``parent_config_id`` is not a legal new
        parent for ``config``; ``(None, None)`` when it is (including a
        ``None`` parent, which clears inheritance)."""
        if parent_config_id is None:
            return None, None
        if not isinstance(parent_config_id, ObjectId):
            return "Invalid parent config id", 400
        if parent_config_id == config["_id"]:
            return "Config cannot be its own parent", 400
        parent = self._configs.find_one({"_id": parent_config_id})
        if parent is None:
            return "Parent config not found", 404
        if parent["project_id"] != project_id:
            return "Parent config must belong to the same project", 400
        if self._would_create_cycle(config["_id"], parent_config_id):
            return "Circular parent reference", 400
        return None, None

    def update(
        self,
        project_id,
        slug,
        name=None,
        parent_config_id=None,
        parent_provided=False,
    ):
        config = self._configs.find_one(
            {"project_id": project_id, "slug": slug}
        )
        if config is None:
            return "Config not found", 404

        update_fields = {}
        if name is not None:
            if not str(name).strip():
                return "Config name is required", 400
            update_fields["name"] = str(name).strip()

        if parent_provided:
            error, code = self._validate_new_parent(
                project_id, config, parent_config_id
            )
            if error:
                return error, code
            update_fields["parent_config_id"] = parent_config_id

        if update_fields:
            self._configs.update_one(
                {"_id": config["_id"]}, {"$set": update_fields}
            )
        return self._configs.find_one({"_id": config["_id"]}), 200

    def delete(self, project_id, slug):
        config = self._configs.find_one(
            {"project_id": project_id, "slug": slug}
        )
        if config is None:
            return "Config not found", 404
        child = self._configs.find_one(
            {"project_id": project_id, "parent_config_id": config["_id"]}
        )
        if child is not None:
            return (
                "Config has child configs; delete or re-parent them first",
                409,
            )
        self._configs.delete_one({"_id": config["_id"]})
        return config, 200

    def delete_all_for_project(self, project_id):
        config_ids = self.list_ids(project_id)
        self._configs.delete_many({"project_id": project_id})
        return config_ids

    def get_by_slug(self, project_id, slug):
        return self._configs.find_one({"project_id": project_id, "slug": slug})

    def get_by_id(self, config_id):
        return self._configs.find_one({"_id": config_id})

    def list_ids(self, project_id):
        docs = self._configs.find({"project_id": project_id}, {"_id": 1})
        return [doc["_id"] for doc in docs if "_id" in doc]

    def list_raw(self, project_id, limit=None):
        cursor = self._configs.find(
            {"project_id": project_id},
            {"_id": 1, "slug": 1, "parent_config_id": 1, "created_at": 1},
        ).sort("slug", 1)
        if limit is not None:
            try:
                parsed_limit = int(limit)
            except (TypeError, ValueError):
                parsed_limit = 0
            if parsed_limit > 0:
                cursor = cursor.limit(parsed_limit)
        return list(cursor)

    def list(self, project_id):
        docs = list(
            self._configs.find(
                {"project_id": project_id},
                {
                    "_id": 1,
                    "slug": 1,
                    "name": 1,
                    "parent_config_id": 1,
                    "created_at": 1,
                },
            ).sort("slug", 1)
        )
        slug_by_id = {doc["_id"]: doc["slug"] for doc in docs}
        configs = []
        for doc in docs:
            parent_id = doc.get("parent_config_id")
            parent_slug = slug_by_id.get(parent_id)
            if parent_id is not None and parent_slug is None:
                parent_doc = self._configs.find_one(
                    {"_id": parent_id, "project_id": project_id}, {"slug": 1}
                )
                parent_slug = parent_doc.get("slug") if parent_doc else None
            configs.append(
                {
                    "slug": doc["slug"],
                    "name": doc.get("name") or doc["slug"],
                    "parentSlug": parent_slug,
                    "createdAt": to_iso(doc.get("created_at")),
                }
            )
        return configs
