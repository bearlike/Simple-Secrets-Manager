#!/usr/bin/env python3
from flask_restx import Resource

from Api.core import api
from Api.versioning import get_application_version

meta_ns = api.namespace("version", description="Application version")


@meta_ns.route("")
class VersionResource(Resource):
    def get(self):
        return {"status": "OK", "version": get_application_version()}, 200
