#!/usr/bin/env python3
"""Token authentication for Secrets Manager."""
import datetime as dt
import hashlib
import os
import secrets

from bson import ObjectId

from Api.serialization import oid_to_str, sanitize_doc, to_iso


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
        return {"token": plain, "status": "OK", "expires_at": to_iso(expires_at), "type": token_type}

    def _resolve_token_doc(self, token=None, token_id=None):
        if token_id:
            try:
                finder = self._tokens.find_one({"_id": ObjectId(token_id)})
            except Exception:
                finder = self._tokens.find_one({"_id": token_id})
            return finder
        if token:
            token_hash = self._hash_token(token)
            return self._tokens.find_one({"token_hash": token_hash})
        return None

    def revoke(self, token=None, username=None, token_id=None):
        finder = self._resolve_token_doc(token=token, token_id=token_id)
        if not finder:
            return {"status": "Token not found"}, 404
        if username and finder.get("subject_user") not in (None, username) and finder.get("created_by") != username:
            return {"status": "Not allowed"}, 403
        self._tokens.update_one(
            {"_id": finder["_id"]}, {"$set": {"revoked_at": dt.datetime.utcnow()}}
        )
        return {"status": "OK"}, 200

    def _serialize_token_metadata(self, doc):
        return {
            "token_id": oid_to_str(doc.get("_id")),
            "type": doc.get("type"),
            "subject_user": doc.get("subject_user"),
            "subject_service_name": doc.get("subject_service_name"),
            "scopes": sanitize_doc(doc.get("scopes", [])),
            "expires_at": to_iso(doc.get("expires_at")),
            "last_used_at": to_iso(doc.get("last_used_at")),
            "revoked_at": to_iso(doc.get("revoked_at")),
            "created_at": to_iso(doc.get("created_at")),
            "created_by": doc.get("created_by"),
        }

    def list_tokens(self):
        cursor = self._tokens.find({}).sort("created_at", -1)
        return [self._serialize_token_metadata(doc) for doc in cursor]

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
            "token_id": oid_to_str(doc.get("_id")),
            "token_type": doc.get("type"),
            "subject_user": doc.get("subject_user"),
            "subject_service_name": doc.get("subject_service_name"),
            "scopes": doc.get("scopes", []),
            "id": oid_to_str(doc.get("_id")),
        }
        return actor, None

    def is_authorized(self, token):
        actor, err = self.authenticate(token)
        if err:
            return False, None
        owner = actor.get("subject_user") or actor.get("subject_service_name")
        return True, owner
