#!/usr/bin/env python3
import os

from flask_restx import fields, Resource

from Api.api import api, conn
from Access.is_auth import require_token, require_scope

userpass_ns = api.namespace(
    name="auth/userpass",
    description="Allows authentication using a username and password.",
)
userpass_model = api.model(
    "Auth Method - Userpass",
    {
        "username": fields.String(required=True, pattern="[a-fA-F0-9_]+", min_length=2),
        "password": fields.String(required=True, min_length=6),
        "status": fields.String(required=False, description="Operation Status"),
    },
)

delete_userpass_parser = api.parser()
delete_userpass_parser.add_argument("username", type=str, required=True, location="form")

post_userpass_parser = api.parser()
post_userpass_parser.add_argument("username", type=str, required=True, location="form")
post_userpass_parser.add_argument("password", type=str, required=True, location="form")


@userpass_ns.route("/delete")
class Auth_Userpass_delete(Resource):
    @api.doc(parser=delete_userpass_parser)
    @api.marshal_with(userpass_model)
    def delete(self):
        args = delete_userpass_parser.parse_args()
        status, code = conn.userpass.remove(username=args["username"])
        if code != 200:
            api.abort(code, status)
        return status


@userpass_ns.route("/register")
class Auth_Userpass_register(Resource):
    @api.doc(parser=post_userpass_parser, security=["Bearer", "Token"])
    @api.marshal_with(userpass_model)
    def post(self):
        open_registration = os.getenv("ALLOW_OPEN_REGISTRATION", "false").lower() == "true"
        if not open_registration:
            require_token()
            require_scope("users:manage")
        args = post_userpass_parser.parse_args()
        status, code = conn.userpass.register(username=args["username"], password=args["password"])
        if code != 200:
            api.abort(code, status)
        return status
