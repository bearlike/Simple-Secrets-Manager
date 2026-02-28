#!/usr/bin/env python3
"""Token authentication for Secrets Manager."""

import datetime as dt
import hashlib
import os
import secrets

from bson import ObjectId

from Api.serialization import oid_to_str, sanitize_doc, to_iso
from Access.scopes import global_scopes


class Tokens:
    SESSION_TOKEN_TTL_SECONDS = 24 * 60 * 60

    def __init__(self, token_auth_col, personal_actor_resolver=None):
        self._tokens = token_auth_col
        self._tokens.create_index("token_hash", unique=True)
        self._tokens.create_index("expires_at")
        self._tokens.create_index("revoked_at")
        self._salt = os.getenv("TOKEN_SALT", "")
        self._personal_actor_resolver = personal_actor_resolver

    def _hash_token(self, token):
        return hashlib.sha256(f"{self._salt}{token}".encode()).hexdigest()

    def _bounded_session_ttl(self, max_ttl):
        try:
            ttl_seconds = int(max_ttl)
        except Exception:
            ttl_seconds = self.SESSION_TOKEN_TTL_SECONDS
        if ttl_seconds <= 0:
            ttl_seconds = self.SESSION_TOKEN_TTL_SECONDS
        return min(ttl_seconds, self.SESSION_TOKEN_TTL_SECONDS)

    def _update_many(self, query, update):
        update_many = getattr(self._tokens, "update_many", None)
        if callable(update_many):
            update_many(query, update)
            return

        finder = getattr(self._tokens, "find", None)
        if not callable(finder):
            return
        for doc in finder(query):
            token_id = doc.get("_id")
            if token_id is None:
                continue
            self._tokens.update_one({"_id": token_id}, update)

    def _rotate_session_tokens(self, username, now):
        self._update_many(
            {
                "type": "personal",
                "subject_user": username,
                "revoked_at": None,
                "$or": [
                    {"purpose": "session"},
                    {"scopes": global_scopes()},
                ],
            },
            {"$set": {"revoked_at": now}},
        )

    def generate(self, username, max_ttl=SESSION_TOKEN_TTL_SECONDS):
        now = dt.datetime.utcnow()
        self._rotate_session_tokens(username, now)
        ttl_seconds = self._bounded_session_ttl(max_ttl)
        expires_at = now + dt.timedelta(seconds=ttl_seconds)
        return self.create_token(
            token_type="personal",
            created_by=username,
            subject_user=username,
            scopes=global_scopes(),
            expires_at=expires_at,
            purpose="session",
        )

    def create_token(
        self,
        token_type,
        created_by,
        scopes,
        subject_user=None,
        subject_service_name=None,
        expires_at=None,
        purpose="api",
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
            "purpose": purpose,
        }
        self._tokens.insert_one(doc)
        return {
            "token": plain,
            "status": "OK",
            "expires_at": to_iso(expires_at),
            "type": token_type,
        }

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
        if (
            username
            and finder.get("subject_user") not in (None, username)
            and finder.get("created_by") != username
        ):
            return {"status": "Not allowed"}, 403
        self._tokens.update_one(
            {"_id": finder["_id"]},
            {"$set": {"revoked_at": dt.datetime.utcnow()}},
        )
        return {"status": "OK"}, 200

    def _serialize_token_metadata(self, doc):
        return {
            "token_id": oid_to_str(doc.get("_id")),
            "type": doc.get("type"),
            "purpose": doc.get("purpose"),
            "subject_user": doc.get("subject_user"),
            "subject_service_name": doc.get("subject_service_name"),
            "scopes": sanitize_doc(doc.get("scopes", [])),
            "expires_at": to_iso(doc.get("expires_at")),
            "last_used_at": to_iso(doc.get("last_used_at")),
            "revoked_at": to_iso(doc.get("revoked_at")),
            "created_at": to_iso(doc.get("created_at")),
            "created_by": doc.get("created_by"),
        }

    def list_tokens(self, include_revoked=False):
        query = {}
        if not include_revoked:
            query = {
                "revoked_at": None,
                "$or": [
                    {"expires_at": None},
                    {"expires_at": {"$gt": dt.datetime.utcnow()}},
                ],
            }
        cursor = self._tokens.find(query).sort("created_at", -1)
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
        self._tokens.update_one(
            {"_id": doc["_id"]},
            {"$set": {"last_used_at": dt.datetime.utcnow()}},
        )
        token_scopes = doc.get("scopes", [])
        effective_scopes = token_scopes
        workspace_role = None
        workspace_id = None
        workspace_slug = None
        visible_project_ids = []
        if doc.get("type") == "personal" and callable(
            self._personal_actor_resolver
        ):
            try:
                actor_context = self._personal_actor_resolver(
                    doc.get("subject_user")
                )
            except Exception:
                actor_context = None

            if isinstance(actor_context, dict):
                if actor_context.get("disabled"):
                    return None, "disabled"
                effective_scopes = actor_context.get(
                    "scopes", effective_scopes
                )
                workspace_role = actor_context.get("workspace_role")
                workspace_id = actor_context.get("workspace_id")
                workspace_slug = actor_context.get("workspace_slug")
                visible_project_ids = list(
                    actor_context.get("visible_project_ids") or []
                )

        actor = {
            "type": "token",
            "token_id": oid_to_str(doc.get("_id")),
            "token_type": doc.get("type"),
            "subject_user": doc.get("subject_user"),
            "subject_service_name": doc.get("subject_service_name"),
            "scopes": effective_scopes,
            "token_scopes": (
                token_scopes
                if doc.get("type") == "personal"
                and str(doc.get("purpose") or "").lower() == "api"
                else None
            ),
            "workspace_role": workspace_role,
            "workspace_id": workspace_id,
            "workspace_slug": workspace_slug,
            "visible_project_ids": visible_project_ids,
            "id": oid_to_str(doc.get("_id")),
        }
        return actor, None

    def is_authorized(self, token):
        actor, err = self.authenticate(token)
        if err:
            return False, None
        owner = actor.get("subject_user") or actor.get("subject_service_name")
        return True, owner
