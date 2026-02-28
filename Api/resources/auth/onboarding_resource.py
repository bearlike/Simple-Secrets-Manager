#!/usr/bin/env python3
from flask_restx import Resource

from Api.core import api, conn

onboarding_ns = api.namespace("onboarding", description="First-time setup")

bootstrap_parser = api.parser()
bootstrap_parser.add_argument(
    "username", type=str, required=True, location="json"
)
bootstrap_parser.add_argument(
    "password", type=str, required=True, location="json"
)


@onboarding_ns.route("/status")
class OnboardingStatusResource(Resource):
    def get(self):
        return {"status": "OK", "onboarding": conn.onboarding.get_state()}, 200


@onboarding_ns.route("/bootstrap")
class OnboardingBootstrapResource(Resource):
    @api.doc(parser=bootstrap_parser)
    def post(self):
        args = bootstrap_parser.parse_args()
        result, code = conn.onboarding.bootstrap(
            username=args["username"],
            password=args["password"],
            issue_token=True,
        )
        if code >= 400:
            api.abort(code, result.get("status", "Bootstrap failed"))
        return result, code
