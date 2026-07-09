#!/usr/bin/env python3
from flask_restx import Resource

from ssm_server.api.core import api
from ssm_server.api.versioning import get_application_version

meta_ns = api.namespace("version", description="Application version")


@meta_ns.route("")
class VersionResource(Resource):
    @staticmethod
    def get():
        return {"status": "OK", "version": get_application_version()}, 200
