#!/usr/bin/env python3
import os

from flask_cors import CORS

from Api.core import app
from Api.resources.secrets.kv_resource import Engine_KV  # noqa: F401
from Api.resources.auth.tokens_resource import Auth_Tokens  # noqa: F401
from Api.resources.auth.tokens_v2_resource import (  # noqa: F401
    ListTokensResource,
    PersonalTokenResource,
    RevokeTokenResource,
    ServiceTokenResource,
)
from Api.resources.auth.onboarding_resource import (  # noqa: F401
    OnboardingBootstrapResource,
    OnboardingStatusResource,
)
from Api.resources.projects.projects_resource import ProjectsResource  # noqa: F401
from Api.resources.configs.configs_resource import ConfigsResource  # noqa: F401
from Api.resources.secrets.secrets_resource import (  # noqa: F401
    SecretExportResource,
    SecretItemResource,
)
from Api.resources.compare.compare_secret_resource import (  # noqa: F401
    CompareSecretResource,
)
from Api.resources.audit.audit_resource import AuditEventsResource  # noqa: F401
from Api.resources.me import MeResource  # noqa: F401
from Api.resources.workspace.workspace_resource import (  # noqa: F401
    WorkspaceGroupItemResource,
    WorkspaceGroupMappingItemResource,
    WorkspaceGroupMappingsResource,
    WorkspaceGroupMembersResource,
    WorkspaceGroupsResource,
    WorkspaceMemberItemResource,
    WorkspaceMembersResource,
    WorkspaceProjectMemberItemResource,
    WorkspaceProjectMembersResource,
    WorkspaceSettingsResource,
)
from Api.resources.auth.userpass_resource import (  # noqa: F401
    Auth_Userpass_delete,
    Auth_Userpass_register,
)
from Api.resources.meta.version_resource import VersionResource  # noqa: F401
from Api.errors import errors  # noqa: F401

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
