#!/usr/bin/env python3
import os

from connection import Connection
from flask import Flask, Blueprint
from flask_cors import CORS
from flask_restx import Api

authorizations = {
    "Token": {"type": "apiKey", "in": "header", "name": "X-API-KEY"},
    "Bearer": {"type": "apiKey", "in": "header", "name": "Authorization"},
    "UserPass": {"type": "basic"},
}

conn = Connection()
api_v1 = Blueprint("api", __name__, url_prefix="/api")
api = Api(
    api_v1,
    version="2.0.0",
    title="Simple Secrets Manager",
    description="Secrets management simplified",
    authorizations=authorizations,
)
app = Flask(__name__)
app.register_blueprint(api_v1)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
CORS(
    app,
    resources={r"/api/*": {"origins": cors_origins or "*"}},
    allow_headers=["Authorization", "Content-Type", "X-API-KEY"],
)

if True:
    from Api.resources.secrets.kv_resource import Engine_KV  # noqa: F401
    from Api.resources.auth.tokens_resource import Auth_Tokens  # noqa: F401
    from Api.resources.auth.tokens_v2_resource import (  # noqa: F401
        ListTokensResource,
        ServiceTokenResource,
        PersonalTokenResource,
        RevokeTokenResource,
    )
    from Api.resources.auth.onboarding_resource import (  # noqa: F401
        OnboardingStatusResource,
        OnboardingBootstrapResource,
    )
    from Api.resources.projects.projects_resource import ProjectsResource  # noqa: F401
    from Api.resources.configs.configs_resource import ConfigsResource  # noqa: F401
    from Api.resources.secrets.secrets_resource import (  # noqa: F401
        SecretItemResource,
        SecretExportResource,
    )
    from Api.resources.compare.compare_secret_resource import (
        CompareSecretResource,  # noqa: F401
    )
    from Api.resources.audit.audit_resource import AuditEventsResource  # noqa: F401
    from Api.resources.me import MeResource  # noqa: F401
    from Api.resources.workspace.workspace_resource import (  # noqa: F401
        WorkspaceSettingsResource,
        WorkspaceMembersResource,
        WorkspaceMemberItemResource,
        WorkspaceProjectMembersResource,
        WorkspaceProjectMemberItemResource,
        WorkspaceGroupsResource,
        WorkspaceGroupItemResource,
        WorkspaceGroupMembersResource,
        WorkspaceGroupMappingsResource,
        WorkspaceGroupMappingItemResource,
    )
    from Api.resources.auth.userpass_resource import (  # noqa: F401
        Auth_Userpass_delete,
        Auth_Userpass_register,
    )
    from Api.resources.meta.version_resource import VersionResource  # noqa: F401
    from Api.errors import errors  # noqa: F401
