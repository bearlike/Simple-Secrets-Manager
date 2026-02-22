#!/usr/bin/env python3
from datetime import datetime, timezone

from Api.serialization import to_iso
from Engines.common import is_valid_slug


class Projects:
    def __init__(self, projects_col):
        self._projects = projects_col
        self._projects.create_index("slug", unique=True)

    def create(self, slug, name):
        if not is_valid_slug(slug):
            return "Invalid project slug", 400
        payload = {
            "slug": slug,
            "name": name or slug,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            self._projects.insert_one(payload)
        except Exception:
            return "Project already exists", 400
        return payload, 201

    def get_by_slug(self, slug):
        return self._projects.find_one({"slug": slug})

    def list(self):
        docs = list(self._projects.find({}, {"_id": 0}).sort("slug", 1))
        for doc in docs:
            doc["created_at"] = to_iso(doc.get("created_at"))
        return docs
