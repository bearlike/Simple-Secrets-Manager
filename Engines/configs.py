#!/usr/bin/env python3
from datetime import datetime, timezone

from bson import ObjectId

from Engines.common import is_valid_slug


class Configs:
    def __init__(self, configs_col):
        self._configs = configs_col
        self._configs.create_index([("project_id", 1), ("slug", 1)], unique=True)

    def create(self, project_id, slug, name, parent_config_id=None):
        if not is_valid_slug(slug):
            return "Invalid config slug", 400
        if parent_config_id is not None and not isinstance(parent_config_id, ObjectId):
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

    def get_by_slug(self, project_id, slug):
        return self._configs.find_one({"project_id": project_id, "slug": slug})

    def get_by_id(self, config_id):
        return self._configs.find_one({"_id": config_id})

    def list(self, project_id):
        return list(self._configs.find({"project_id": project_id}, {"_id": 0, "project_id": 0}))
