#!/usr/bin/env python3
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError

from Api.serialization import to_iso
from Access.scopes import DEFAULT_TOKEN_ACTION_SCOPES, global_scopes


class Onboarding:
    DOC_ID = "bootstrap_state_v1"
    BOOTSTRAP_TOKEN_TTL_SECONDS = 15811200
    BOOTSTRAP_ACTION_SCOPES = DEFAULT_TOKEN_ACTION_SCOPES

    def __init__(
        self,
        state_col,
        userpass_engine,
        tokens_engine,
        workspaces_engine=None,
        users_engine=None,
        memberships_engine=None,
    ):
        self._state = state_col
        self._userpass = userpass_engine
        self._tokens = tokens_engine
        self._workspaces = workspaces_engine
        self._users = users_engine
        self._memberships = memberships_engine
        self._state.create_index("status")

    def _doc(self):
        return self._state.find_one({"_id": self.DOC_ID})

    def _mark_failed(self, error_message):
        self._state.update_one(
            {"_id": self.DOC_ID},
            {
                "$set": {
                    "status": "failed",
                    "failed_at": datetime.now(timezone.utc),
                    "error": str(error_message),
                }
            },
        )

    def _acquire_lock(self):
        now = datetime.now(timezone.utc)
        try:
            self._state.insert_one(
                {
                    "_id": self.DOC_ID,
                    "status": "in_progress",
                    "started_at": now,
                }
            )
            return None, None
        except DuplicateKeyError:
            doc = self._doc()
            if not doc:
                return "Bootstrap lock error. Please retry.", 409
            status = doc.get("status")
            if status == "completed":
                return "System already initialized", 409
            if status == "in_progress":
                return "Bootstrap already in progress", 409
            self._state.update_one(
                {"_id": self.DOC_ID},
                {
                    "$set": {
                        "status": "in_progress",
                        "started_at": now,
                    },
                    "$unset": {
                        "error": "",
                        "failed_at": "",
                    },
                },
            )
            return None, None

    def get_state(self):
        doc = self._doc()
        if not doc:
            return {
                "isInitialized": False,
                "state": "not_initialized",
                "initializedAt": None,
                "initializedBy": None,
            }
        status = doc.get("status")
        return {
            "isInitialized": status == "completed",
            "state": status or "unknown",
            "initializedAt": to_iso(doc.get("initialized_at")),
            "initializedBy": doc.get("initialized_by"),
        }

    def is_initialized(self):
        return self.get_state().get("isInitialized", False)

    def bootstrap(self, username, password, issue_token=True):
        error, code = self._acquire_lock()
        if error:
            return {"status": error}, code

        register_status, register_code = self._userpass.register(
            username=username, password=password
        )
        if register_code != 200:
            # Allow retry when user was created in a previous failed bootstrap
            # attempt.
            if (
                register_status == "User already exist"
                and self._userpass.is_authorized(username, password)
            ):
                pass
            else:
                self._mark_failed(register_status)
                return {"status": str(register_status)}, register_code

        if (
            self._workspaces is not None
            and self._users is not None
            and self._memberships is not None
        ):
            workspace = self._workspaces.ensure_default()
            workspace_id = workspace.get("_id") if workspace else None
            if workspace_id is not None:
                self._users.ensure(username)
                self._memberships.upsert_workspace_membership(
                    workspace_id, username, "owner"
                )

        token_payload = None
        if issue_token:
            try:
                token_payload = self._tokens.create_token(
                    token_type="personal",
                    created_by=username,
                    subject_user=username,
                    scopes=global_scopes(self.BOOTSTRAP_ACTION_SCOPES),
                    expires_at=datetime.utcnow()
                    + timedelta(seconds=self.BOOTSTRAP_TOKEN_TTL_SECONDS),
                )
            except Exception as exc:  # pragma: no cover - defensive path
                self._mark_failed(exc)
                return {"status": "Failed to generate bootstrap token"}, 500

        now = datetime.now(timezone.utc)
        self._state.update_one(
            {"_id": self.DOC_ID},
            {
                "$set": {
                    "status": "completed",
                    "initialized_at": now,
                    "initialized_by": username,
                },
                "$unset": {
                    "error": "",
                    "failed_at": "",
                },
            },
        )

        result = {"status": "OK", "onboarding": self.get_state()}
        if token_payload:
            result.update(
                {
                    "token": token_payload.get("token"),
                    "expires_at": token_payload.get("expires_at"),
                    "type": token_payload.get("type"),
                }
            )
            return result, 201
        return result, 200
