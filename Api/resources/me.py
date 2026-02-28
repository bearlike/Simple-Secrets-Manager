#!/usr/bin/env python3
from flask import g, request
from flask_restx import Resource

from Api.api import api, conn
from Access.is_auth import with_token

me_ns = api.namespace("me", description="Current authenticated user")

profile_update_parser = api.parser()
profile_update_parser.add_argument(
    "email", type=str, required=False, location="json"
)
profile_update_parser.add_argument(
    "fullName", type=str, required=False, location="json"
)


def _serialize_me(username):
    actor_context = conn.rbac.resolve_personal_actor(username)
    user = conn.users.ensure(username)
    return {
        "status": "OK",
        "username": username,
        "email": user.get("email"),
        "fullName": user.get("full_name"),
        "workspaceRole": actor_context.get("workspace_role"),
        "workspaceSlug": actor_context.get("workspace_slug"),
        "effectivePermissionsSummary": conn.rbac.summarize_scopes(
            actor_context.get("scopes") or []
        ),
    }


@me_ns.route("")
class MeResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self):
        username = g.actor.get("subject_user")
        if not username:
            api.abort(403, "Service tokens do not have a user profile")
        return _serialize_me(username), 200

    @api.doc(security=["Bearer", "Token"], parser=profile_update_parser)
    @with_token
    def patch(self):
        username = g.actor.get("subject_user")
        if not username:
            api.abort(403, "Service tokens do not have a user profile")

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            api.abort(400, "Invalid JSON payload")

        allowed = {"email", "fullName"}
        unknown_fields = [field for field in payload if field not in allowed]
        if unknown_fields:
            api.abort(
                400, f"Unknown fields: {', '.join(sorted(unknown_fields))}"
            )

        email = payload.get("email") if "email" in payload else None
        full_name = payload.get("fullName") if "fullName" in payload else None

        _, msg, code = conn.users.update_profile(
            username, email=email, full_name=full_name
        )
        if code >= 400:
            api.abort(code, msg)

        return _serialize_me(username), 200
