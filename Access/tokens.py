#!/usr/bin/env python3
"""Token authentication for Secrets Manager."""
import datetime as dt
import hashlib
import os
import secrets


class Tokens:
    def __init__(self, token_auth_col):
        self._tokens = token_auth_col
        self._tokens.create_index("token_hash", unique=True)
        self._tokens.create_index("expires_at")
        self._tokens.create_index("revoked_at")
        self._salt = os.getenv("TOKEN_SALT", "")

    def _hash_token(self, token):
        return hashlib.sha256(f"{self._salt}{token}".encode()).hexdigest()

    def generate(self, username, max_ttl=15811200):
        expires_at = dt.datetime.utcnow() + dt.timedelta(seconds=max_ttl)
        return self.create_token(
            token_type="personal",
            created_by=username,
            subject_user=username,
            scopes=[],
            expires_at=expires_at,
        )

    def create_token(
        self,
        token_type,
        created_by,
        scopes,
        subject_user=None,
        subject_service_name=None,
        expires_at=None,
    ):
        plain = secrets.token_hex(32)
        now = dt.datetime.utcnow()
        doc = {
            "token_hash": self._hash_token(plain),
            "type": token_type,
            "subject_user": subject_user,
            "subject_service_name": subject_service_name,
            "scopes": scopes or [],
            "expires_at": expires_at,
            "created_at": now,
            "created_by": created_by,
            "last_used_at": None,
            "revoked_at": None,
        }
        self._tokens.insert_one(doc)
        return {"token": plain, "status": "OK", "expires_at": expires_at, "type": token_type}

    def revoke(self, token, username=None):
        token_hash = self._hash_token(token)
        finder = self._tokens.find_one({"token_hash": token_hash})
        if not finder:
            return {"status": "Token not found"}, 404
        if username and finder.get("subject_user") not in (None, username) and finder.get("created_by") != username:
            return {"status": "Not allowed"}, 403
        self._tokens.update_one(
            {"_id": finder["_id"]}, {"$set": {"revoked_at": dt.datetime.utcnow()}}
        )
        return {"status": "OK"}, 200

    def authenticate(self, token):
        token_hash = self._hash_token(token)
        doc = self._tokens.find_one({"token_hash": token_hash})
        if not doc:
            return None, "invalid"
        if doc.get("revoked_at") is not None:
            return None, "revoked"
        expires_at = doc.get("expires_at")
        if expires_at is not None and expires_at < dt.datetime.utcnow():
            return None, "expired"
        self._tokens.update_one({"_id": doc["_id"]}, {"$set": {"last_used_at": dt.datetime.utcnow()}})
        actor = {
            "type": "token",
            "token_id": str(doc["_id"]),
            "token_type": doc.get("type"),
            "subject_user": doc.get("subject_user"),
            "subject_service_name": doc.get("subject_service_name"),
            "scopes": doc.get("scopes", []),
            "id": str(doc["_id"]),
        }
        return actor, None

    def is_authorized(self, token):
        actor, err = self.authenticate(token)
        if err:
            return False, None
        owner = actor.get("subject_user") or actor.get("subject_service_name")
        return True, owner
