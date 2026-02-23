#!/usr/bin/env python3
"""Database model for the Secrets Manager"""

import os
import sys
import pymongo
from loguru import logger

from Engines.kv import Key_Value_Secrets as _KV
from Engines.projects import Projects as _Projects
from Engines.configs import Configs as _Configs
from Engines.secrets_v2 import SecretsV2 as _SecretsV2
from Engines.audit import AuditEvents as _AuditEvents

from Access.tokens import Tokens as _Tokens
from Access.userpass import User_Pass as _User_Pass


class __connection:
    def __init__(self):
        if os.environ.get("CONNECTION_STRING") is None:
            logger.error("CONNECTION_STRING variable not found")
            sys.exit(-1)
        self.__client = pymongo.MongoClient(os.environ["CONNECTION_STRING"])
        self.__data = self.__client["secrets_manager_data"]
        self.__auth = self.__client["secrets_manager_auth"]

        self.kv = _KV(self.__data["kv"])
        self.projects = _Projects(self.__data["projects"])
        self.configs = _Configs(self.__data["configs"])
        self.secrets_v2 = _SecretsV2(self.__data["secrets"], self.configs)
        self.audit = _AuditEvents(self.__data["audit_events"])

        self.tokens = _Tokens(self.__auth["tokens"])
        self.userpass = _User_Pass(self.__auth["userpass"])


class Connection(__connection):
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(Connection, cls).__new__(cls)
        return cls.instance
