#!/usr/bin/env python3
from flask import jsonify
from Api.core import app


# Use the same {"message": ...} envelope that flask-restx produces for
# aborts, so every error response the API emits is shaped identically for
# API and CLI consumers (both read "message" first).
@app.errorhandler(404)
def not_found(_error):
    return jsonify(message="Resource not found"), 404


@app.errorhandler(Exception)
def server_error(error):
    app.logger.exception(error)
    return jsonify(message="Server error. Contact administrator"), 500
