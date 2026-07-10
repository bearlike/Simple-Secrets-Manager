#!/usr/bin/env python3
"""Database model for the Secrets Manager"""

import pymongo

from ssm_server.engines.kv import Key_Value_Secrets as _KV
from ssm_server.engines.projects import Projects as _Projects
from ssm_server.engines.configs import Configs as _Configs
from ssm_server.engines.secrets_v2 import SecretsV2 as _SecretsV2
from ssm_server.engines.audit import AuditEvents as _AuditEvents
from ssm_server.engines.reload_status import ReloadStatus as _ReloadStatus
from ssm_server.engines.workspaces import Workspaces as _Workspaces
from ssm_server.engines.users import Users as _Users
from ssm_server.engines.memberships import Memberships as _Memberships
from ssm_server.engines.groups import Groups as _Groups
from ssm_server.engines.rbac import RBAC as _RBAC

from ssm_server.access.tokens import Tokens as _Tokens
from ssm_server.access.userpass import User_Pass as _User_Pass
from ssm_server.access.onboarding import Onboarding as _Onboarding


class __connection:
    def __init__(self, settings):
        # `settings` is a ssm_server.settings.ServerSettings, injected by
        # ssm_server.api.core (the one place it is built). Kept untyped to
        # match this module's legacy style; the salt stays a SecretStr until
        # Tokens unwraps it at the hashing point.
        # tz_aware=True so datetimes read back from Mongo are timezone-aware
        # (UTC), matching what every engine/access writer now stores
        # (datetime.now(timezone.utc)). Without it, read-back values are NAIVE
        # and comparing them against an aware `now` (e.g. token-expiry checks)
        # raises TypeError. Storage is unaffected — Mongo persists UTC millis
        # either way, including legacy docs written via the old utcnow().
        self.__client = pymongo.MongoClient(
            settings.connection_string, tz_aware=True
        )
        self.__data = self.__client["secrets_manager_data"]
        self.__auth = self.__client["secrets_manager_auth"]

        self.kv = _KV(self.__data["kv"])
        self.workspaces = _Workspaces(self.__auth["workspaces"])
        self.users = _Users(self.__auth["users"])
        self.memberships = _Memberships(
            self.__auth["workspace_memberships"],
            self.__auth["project_memberships"],
        )
        self.groups = _Groups(
            self.__auth["groups"],
            self.__auth["group_members"],
            self.__auth["group_mappings"],
            memberships_engine=self.memberships,
        )

        self.projects = _Projects(
            self.__data["projects"], workspaces_engine=self.workspaces
        )
        self.configs = _Configs(self.__data["configs"])
        self.secrets_v2 = _SecretsV2(self.__data["secrets"], self.configs)
        self.audit = _AuditEvents(self.__data["audit_events"])
        self.reload_status = _ReloadStatus(self.__data["reload_status"])

        self.rbac = _RBAC(
            self.workspaces,
            self.users,
            self.memberships,
            self.groups,
            self.projects,
            onboarding_state_col=self.__auth["system_state"],
        )
        self.tokens = _Tokens(
            self.__auth["tokens"],
            personal_actor_resolver=self.rbac.resolve_personal_actor,
            token_salt=settings.token_salt,
        )
        self.userpass = _User_Pass(self.__auth["userpass"])
        self.onboarding = _Onboarding(
            self.__auth["system_state"],
            self.userpass,
            self.tokens,
            workspaces_engine=self.workspaces,
            users_engine=self.users,
            memberships_engine=self.memberships,
        )


class Connection(__connection):
    # `__init__` takes the settings object; `__new__` only enforces the
    # singleton, so it ignores the constructor args.
    def __new__(cls, *_args, **_kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = super(Connection, cls).__new__(cls)
        return cls.instance
