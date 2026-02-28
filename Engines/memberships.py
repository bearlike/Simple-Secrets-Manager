#!/usr/bin/env python3
from datetime import datetime, timezone

from bson import ObjectId

WORKSPACE_ROLES = ("owner", "admin", "collaborator", "viewer")
PROJECT_ROLES = ("admin", "collaborator", "viewer", "none")
SUBJECT_TYPES = ("user", "group")


class Memberships:
    def __init__(self, workspace_memberships_col, project_memberships_col):
        self._workspace_memberships = workspace_memberships_col
        self._project_memberships = project_memberships_col

        self._workspace_memberships.create_index(
            [("workspace_id", 1), ("username", 1)], unique=True
        )
        self._project_memberships.create_index(
            [
                ("workspace_id", 1),
                ("project_id", 1),
                ("subject_type", 1),
                ("subject_id", 1),
            ],
            unique=True,
        )

    def count_workspace_members(self, workspace_id):
        return int(
            self._workspace_memberships.count_documents(
                {"workspace_id": workspace_id}
            )
        )

    def has_workspace_role(self, workspace_id, workspace_role):
        return (
            int(
                self._workspace_memberships.count_documents(
                    {
                        "workspace_id": workspace_id,
                        "workspace_role": workspace_role,
                    }
                )
            )
            > 0
        )

    def get_workspace_membership(self, workspace_id, username):
        return self._workspace_memberships.find_one(
            {"workspace_id": workspace_id, "username": username}
        )

    def list_workspace_memberships(self, workspace_id):
        return list(
            self._workspace_memberships.find(
                {"workspace_id": workspace_id}
            ).sort("username", 1)
        )

    def upsert_workspace_membership(
        self, workspace_id, username, workspace_role
    ):
        if workspace_role not in WORKSPACE_ROLES:
            return None, "Invalid workspace role", 400

        self._workspace_memberships.update_one(
            {"workspace_id": workspace_id, "username": username},
            {
                "$set": {
                    "workspace_role": workspace_role,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "workspace_id": workspace_id,
                    "username": username,
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        return self.get_workspace_membership(workspace_id, username), "OK", 200

    def remove_workspace_membership(self, workspace_id, username):
        res = self._workspace_memberships.delete_one(
            {"workspace_id": workspace_id, "username": username}
        )
        if res.deleted_count == 0:
            return "Membership not found", 404
        return "OK", 200

    def upsert_project_membership(
        self, workspace_id, project_id, subject_type, subject_id, project_role
    ):
        if subject_type not in SUBJECT_TYPES:
            return None, "Invalid subject type", 400
        if project_role not in PROJECT_ROLES:
            return None, "Invalid project role", 400
        if not subject_id:
            return None, "subject_id is required", 400

        self._project_memberships.update_one(
            {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "subject_type": subject_type,
                "subject_id": subject_id,
            },
            {
                "$set": {
                    "project_role": project_role,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "workspace_id": workspace_id,
                    "project_id": project_id,
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        return (
            self._project_memberships.find_one(
                {
                    "workspace_id": workspace_id,
                    "project_id": project_id,
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                }
            ),
            "OK",
            200,
        )

    def remove_project_membership(
        self, workspace_id, project_id, subject_type, subject_id
    ):
        res = self._project_memberships.delete_one(
            {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "subject_type": subject_type,
                "subject_id": subject_id,
            }
        )
        if res.deleted_count == 0:
            return "Membership not found", 404
        return "OK", 200

    def list_project_memberships(self, workspace_id, project_id):
        return list(
            self._project_memberships.find(
                {"workspace_id": workspace_id, "project_id": project_id}
            ).sort("subject_id", 1)
        )

    def list_project_memberships_for_subjects(
        self, workspace_id, username, group_ids
    ):
        normalized_group_ids = set()
        for group_id in group_ids or []:
            normalized_group_ids.add(group_id)
            normalized_group_ids.add(str(group_id))
            if isinstance(group_id, str):
                try:
                    normalized_group_ids.add(ObjectId(group_id))
                except Exception:
                    pass

        clauses = [{"subject_type": "user", "subject_id": username}]
        if normalized_group_ids:
            clauses.append(
                {
                    "subject_type": "group",
                    "subject_id": {"$in": list(normalized_group_ids)},
                }
            )

        return list(
            self._project_memberships.find(
                {
                    "workspace_id": workspace_id,
                    "$or": clauses,
                }
            )
        )

    def remove_all_for_subject(self, workspace_id, subject_type, subject_id):
        self._project_memberships.delete_many(
            {
                "workspace_id": workspace_id,
                "subject_type": subject_type,
                "subject_id": subject_id,
            }
        )
