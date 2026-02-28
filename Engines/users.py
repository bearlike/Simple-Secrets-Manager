#!/usr/bin/env python3
from datetime import datetime, timezone


class Users:
    def __init__(self, users_col):
        self._users = users_col
        self._users.create_index("username", unique=True)

    @staticmethod
    def _normalize_email(value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _normalize_full_name(value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def get(self, username):
        return self._users.find_one({"username": username})

    def list(self):
        return list(self._users.find({}).sort("username", 1))

    def create(self, username, email=None, full_name=None):
        if not username:
            return None, "Username is required", 400
        payload = {
            "username": username,
            "email": self._normalize_email(email),
            "full_name": self._normalize_full_name(full_name),
            "created_at": datetime.now(timezone.utc),
            "disabled_at": None,
        }
        try:
            self._users.insert_one(payload)
        except Exception:
            return None, "User already exists", 400
        return payload, "OK", 201

    def ensure(self, username, email=None, full_name=None):
        existing = self.get(username)
        if existing:
            return existing
        payload, _, code = self.create(username, email=email, full_name=full_name)
        if code >= 400:
            return self.get(username)
        return payload

    def update_profile(self, username, email=None, full_name=None):
        doc = self.get(username)
        if not doc:
            return None, "User not found", 404

        updates = {}
        if email is not None:
            updates["email"] = self._normalize_email(email)
        if full_name is not None:
            updates["full_name"] = self._normalize_full_name(full_name)

        if updates:
            updates["updated_at"] = datetime.now(timezone.utc)
            self._users.update_one({"username": username}, {"$set": updates})

        return self.get(username), "OK", 200

    def set_disabled(self, username, disabled):
        doc = self.get(username)
        if not doc:
            return None, "User not found", 404

        updates = {"updated_at": datetime.now(timezone.utc)}
        updates["disabled_at"] = datetime.now(timezone.utc) if disabled else None
        self._users.update_one({"username": username}, {"$set": updates})
        return self.get(username), "OK", 200

    def delete(self, username):
        res = self._users.delete_one({"username": username})
        if res.deleted_count == 0:
            return "User not found", 404
        return "OK", 200

    def is_disabled(self, username):
        user = self.get(username)
        return bool(user and user.get("disabled_at") is not None)
