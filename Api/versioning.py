#!/usr/bin/env python3
from Engines.versioning import get_application_version as _get_application_version


def get_application_version() -> str:
    return _get_application_version()
