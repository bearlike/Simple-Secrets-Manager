#!/usr/bin/env python3
from flask import jsonify
from Api.core import app


@app.errorhandler(404)
def not_found(_error):
    return jsonify(error="Resource not found"), 404


@app.errorhandler(Exception)
def server_error(error):
    app.logger.exception(error)
    return jsonify(error="Server error. Contact administrator"), 500
