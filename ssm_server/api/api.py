#!/usr/bin/env python3
import os

from flask_cors import CORS

from ssm_server.api.core import app
from ssm_server.api.resources.secrets.kv_resource import Engine_KV  # noqa: F401
from ssm_server.api.resources.auth.tokens_resource import Auth_Tokens  # noqa: F401
from ssm_server.api.resources.auth.tokens_v2_resource import (  # noqa: F401
    ListTokensResource,
    PersonalTokenResource,
    RevokeTokenResource,
    ServiceTokenResource,
)
from ssm_server.api.resources.auth.onboarding_resource import (  # noqa: F401
    OnboardingBootstrapResource,
    OnboardingStatusResource,
)
from ssm_server.api.resources.projects.projects_resource import (  # noqa: F401
    ProjectItemResource,
    ProjectsResource,
)
from ssm_server.api.resources.configs.configs_resource import (  # noqa: F401
    ConfigItemResource,
    ConfigsResource,
)
from ssm_server.api.resources.secrets.secrets_resource import (  # noqa: F401
    SecretExportResource,
    SecretItemResource,
)
from ssm_server.api.resources.secrets.project_icons_resource import (  # noqa: F401
    ProjectSecretIconsRecomputeResource,
)
from ssm_server.api.resources.compare.compare_secret_resource import (  # noqa: F401
    CompareSecretResource,
)
from ssm_server.api.resources.audit.audit_resource import AuditEventsResource  # noqa: F401
from ssm_server.api.resources.reload.reload_resource import (  # noqa: F401
    ReloadEventsResource,
)
from ssm_server.api.resources.me import MeResource  # noqa: F401
from ssm_server.api.resources.workspace.workspace_resource import (  # noqa: F401
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
from ssm_server.api.resources.auth.userpass_resource import (  # noqa: F401
    Auth_Userpass_delete,
    Auth_Userpass_register,
)
from ssm_server.api.resources.meta.version_resource import VersionResource  # noqa: F401
from ssm_server.api.errors import errors  # noqa: F401

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
