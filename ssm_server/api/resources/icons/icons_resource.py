#!/usr/bin/env python3
"""Read-only icon catalog for the secret-icon picker.

Serves the per-pack prefix/name lists derived from the precomputed icon
index. These endpoints gate on ``@with_token`` only and deliberately skip
``require_scope``: the catalog is static Iconify metadata, identical for every
tenant, so it exposes no project/config data and needs no per-scope check. No
audit events are written for the same reason — it is a metadata read, not a
secret access.
"""

from flask_restx import Resource

from ssm_server.api.core import api
from ssm_server.access.is_auth import with_token
from ssm_server.engines.secret_icons import (
    is_valid_icon_prefix,
    list_icon_names,
    list_icon_prefixes,
)

icons_ns = api.namespace("icons", description="Icon catalog for secret icons")


@icons_ns.route("/prefixes")
class IconPrefixesResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self):
        return {"status": "OK", "prefixes": list_icon_prefixes()}, 200


@icons_ns.route("/prefixes/<string:prefix>/names")
class IconPackNamesResource(Resource):
    @api.doc(security=["Bearer", "Token"])
    @with_token
    def get(self, prefix):
        if not is_valid_icon_prefix(prefix):
            api.abort(404, "Icon prefix not found")
        names = list_icon_names(prefix)
        if not names:
            api.abort(404, "Icon prefix not found")
        return {"status": "OK", "prefix": prefix, "names": names}, 200
