#!/usr/bin/env python3
from connection import Connection
from flask import Blueprint, Flask
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
