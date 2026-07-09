"""The Flask API server component of Simple Secrets Manager.

Bundles the HTTP boundary (``ssm_server.api``), the business-logic engines
(``ssm_server.engines``), the auth/RBAC layer (``ssm_server.access``), and
the shared Mongo wiring (``ssm_server.connection``). Run the dev server with
``python -m ssm_server.main``.
"""
