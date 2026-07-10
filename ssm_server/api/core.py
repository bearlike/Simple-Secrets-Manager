#!/usr/bin/env python3
import sys

from flask import Blueprint, Flask
from flask_restx import Api
from loguru import logger
from pydantic import ValidationError

from ssm_server.connection import Connection
from ssm_server.settings import ServerSettings

authorizations = {
    "Token": {"type": "apiKey", "in": "header", "name": "X-API-KEY"},
    "Bearer": {"type": "apiKey", "in": "header", "name": "Authorization"},
    "UserPass": {"type": "basic"},
}


def _load_settings() -> ServerSettings:
    """Validate configuration once at start-up, failing fast and clean.

    A bad/missing env var must not surface as a raw pydantic traceback: log a
    single-line loguru error and exit non-zero, matching the API's clean
    error style. Runs at module import (before ``Connection`` opens Mongo).
    """
    try:
        # pydantic-settings populates every field from the environment; mypy
        # can't see that, so it reads the required fields as missing kwargs.
        return ServerSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        )
        logger.error("Invalid server configuration: {}", detail)
        sys.exit(1)


settings = _load_settings()
conn = Connection(settings)
api_v1 = Blueprint("api", __name__, url_prefix="/api")
api = Api(
    api_v1,
    version="2.0.0",
    title="Simple Secrets Manager",
    description="Secrets management simplified",
    authorizations=authorizations,
)
app = Flask(__name__)
# Do not append flask-restx's "did you mean <route template>" help text to
# 404 responses. It leaks internal URL patterns and turns clean messages
# like "Project not found" into noise for API and CLI consumers.
app.config["RESTX_ERROR_404_HELP"] = False
app.register_blueprint(api_v1)
