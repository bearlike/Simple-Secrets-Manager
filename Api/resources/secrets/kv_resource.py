#!/usr/bin/env python3
# Key-Value (KV) Secrets Engines API Resource
from flask_restx import fields, Resource
from Api.api import api, conn
from Access.is_auth import require_token

# KV Namespace
kv_ns = api.namespace(
    name="secrets/kv",
    description="Key-Value (KV) engine is used to store arbitrary secrets",
)
kv_model = api.model(
    "Secrets Engine - KV",
    {
        "path": fields.String(
            required=True,
            pattern="[a-zA-Z0-9_]+",
            min_length=1,
            description="Path to the kv datastore",
        ),
        "key": fields.String(
            required=True,
            pattern="[a-zA-Z0-9_]+",
            min_length=1,
            description="Key (index) in path where a secret is stored",
        ),
        "value": fields.String(
            required=True,
            description="Secret (value) for the corresponding Key in Path",
        ),
        "status": fields.String(required=False, description="Operation Status"),
    },
)

# KV Arguments
kv_parser = api.parser()
kv_parser.add_argument(
    "value",
    type=str,
    required=True,
    location="form",
    help="Secret (value) for the corresponding Key (index) in Path",
)


@kv_ns.route("/<string:path>/<string:key>")
@api.doc(
    responses={401: "Unauthorized", 404: "Path or KV not found"},
    params={
        "path": "Path to a KV store",
        "key": "Key (index) in path where a secret (value) is stored",
    },
)
class Engine_KV(Resource):
    """Key-Value API operations"""

    @api.doc(description="Update a kv in a path", security="Token", parser=kv_parser)
    @api.marshal_with(kv_model)
    def put(self, path, key):
        """Update a given resource"""
        args = kv_parser.parse_args()
        require_token()
        status, code = conn.kv.update(path, key, args["value"])
        if code != 200:
            api.abort(code, status)
            return None
        return status

    @api.doc(
        description="Delete a KV from a path",
        security="Token",
        responses={200: "Secrets deleted"},
    )
    def delete(self, path, key):
        """Delete a given kv"""
        require_token()
        status, code = conn.kv.delete(path, key)
        if code != 200:
            api.abort(code, status)
            return None
        return status

    @api.doc(description="Add a KV to a path", security="Token", parser=kv_parser)
    @api.marshal_with(kv_model)
    def post(self, path, key):
        """Add a new kv to a path"""
        args = kv_parser.parse_args()
        require_token()
        status, code = conn.kv.add(path, key, args["value"])
        if code != 200:
            api.abort(code, status)
            return None
        return status

    @api.doc(description="Return a KV from a path", security="Token")
    @api.marshal_with(kv_model)
    def get(self, path, key):
        """Fetch a given KV from a path"""
        require_token()
        status, code = conn.kv.get(path, key)
        if code != 200:
            api.abort(code, str(status))
        return status
