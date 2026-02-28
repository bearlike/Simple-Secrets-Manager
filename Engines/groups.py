#!/usr/bin/env python3
from datetime import datetime, timezone

from bson import ObjectId

from Engines.common import is_valid_slug

SUPPORTED_MAPPING_PROVIDERS = ("manual",)


class Groups:
    def __init__(self, groups_col, group_members_col, group_mappings_col, memberships_engine=None):
        self._groups = groups_col
        self._group_members = group_members_col
        self._group_mappings = group_mappings_col
        self._memberships = memberships_engine

        self._groups.create_index([("workspace_id", 1), ("slug", 1)], unique=True)
        self._group_members.create_index([("workspace_id", 1), ("group_id", 1), ("username", 1)], unique=True)
        self._group_mappings.create_index(
            [("workspace_id", 1), ("provider", 1), ("external_group_key", 1)],
            unique=True,
        )

    def _get_by_slug(self, workspace_id, group_slug):
        return self._groups.find_one({"workspace_id": workspace_id, "slug": group_slug})

    def get_by_slug(self, workspace_id, group_slug):
        return self._get_by_slug(workspace_id, group_slug)

    def get_by_id(self, workspace_id, group_id):
        try:
            lookup_id = ObjectId(group_id)
        except Exception:
            lookup_id = group_id
        return self._groups.find_one({"workspace_id": workspace_id, "_id": lookup_id})

    def list_groups(self, workspace_id):
        return list(self._groups.find({"workspace_id": workspace_id}).sort("slug", 1))

    def create_group(self, workspace_id, slug, name=None, description=None):
        if not is_valid_slug(slug):
            return None, "Invalid group slug", 400

        payload = {
            "workspace_id": workspace_id,
            "slug": slug,
            "name": (name or slug).strip(),
            "description": (description or "").strip() or None,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            self._groups.insert_one(payload)
        except Exception:
            return None, "Group already exists", 400
        return payload, "OK", 201

    def update_group(self, workspace_id, group_slug, name=None, description=None):
        group = self._get_by_slug(workspace_id, group_slug)
        if not group:
            return None, "Group not found", 404

        updates = {"updated_at": datetime.now(timezone.utc)}
        if name is not None:
            normalized_name = str(name).strip()
            if not normalized_name:
                return None, "Group name cannot be empty", 400
            updates["name"] = normalized_name
        if description is not None:
            updates["description"] = str(description).strip() or None

        self._groups.update_one({"_id": group["_id"]}, {"$set": updates})
        return self._get_by_slug(workspace_id, group_slug), "OK", 200

    def delete_group(self, workspace_id, group_slug):
        group = self._get_by_slug(workspace_id, group_slug)
        if not group:
            return "Group not found", 404

        group_id = group["_id"]
        self._group_members.delete_many({"workspace_id": workspace_id, "group_id": group_id})
        self._group_mappings.delete_many({"workspace_id": workspace_id, "group_id": group_id})
        if self._memberships is not None:
            self._memberships.remove_all_for_subject(workspace_id, "group", str(group_id))

        self._groups.delete_one({"_id": group_id})
        return "OK", 200

    def list_group_members(self, workspace_id, group_id):
        return list(self._group_members.find({"workspace_id": workspace_id, "group_id": group_id}).sort("username", 1))

    def update_group_members(self, workspace_id, group_slug, add=None, remove=None):
        group = self._get_by_slug(workspace_id, group_slug)
        if not group:
            return None, "Group not found", 404

        group_id = group["_id"]
        add = add or []
        remove = remove or []

        for username in add:
            if not isinstance(username, str) or not username.strip():
                return None, "Invalid username in add list", 400
            self._group_members.update_one(
                {
                    "workspace_id": workspace_id,
                    "group_id": group_id,
                    "username": username,
                },
                {
                    "$setOnInsert": {
                        "workspace_id": workspace_id,
                        "group_id": group_id,
                        "username": username,
                        "created_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )

        for username in remove:
            self._group_members.delete_one(
                {
                    "workspace_id": workspace_id,
                    "group_id": group_id,
                    "username": username,
                }
            )

        members = self.list_group_members(workspace_id, group_id)
        return members, "OK", 200

    def list_user_group_ids(self, workspace_id, username):
        docs = self._group_members.find(
            {
                "workspace_id": workspace_id,
                "username": username,
            },
            {"group_id": 1},
        )
        return [str(doc["group_id"]) for doc in docs if doc.get("group_id") is not None]

    def remove_user_from_all_groups(self, workspace_id, username):
        self._group_members.delete_many({"workspace_id": workspace_id, "username": username})

    def list_group_mappings(self, workspace_id):
        return list(self._group_mappings.find({"workspace_id": workspace_id}).sort("external_group_key", 1))

    def create_group_mapping(self, workspace_id, provider, external_group_key, group_slug):
        if provider not in SUPPORTED_MAPPING_PROVIDERS:
            return None, "Unsupported mapping provider", 400
        normalized_key = str(external_group_key or "").strip()
        if not normalized_key:
            return None, "externalGroupKey is required", 400

        group = self._get_by_slug(workspace_id, group_slug)
        if not group:
            return None, "Group not found", 404

        payload = {
            "workspace_id": workspace_id,
            "provider": provider,
            "external_group_key": normalized_key,
            "group_id": group["_id"],
            "created_at": datetime.now(timezone.utc),
        }
        try:
            self._group_mappings.insert_one(payload)
        except Exception:
            return None, "Group mapping already exists", 400
        return payload, "OK", 201

    def delete_group_mapping(self, workspace_id, mapping_id):
        try:
            lookup_id = ObjectId(mapping_id)
        except Exception:
            lookup_id = mapping_id

        res = self._group_mappings.delete_one({"workspace_id": workspace_id, "_id": lookup_id})
        if res.deleted_count == 0:
            return "Group mapping not found", 404
        return "OK", 200
