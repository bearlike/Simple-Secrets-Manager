"""Hermetic tests for the `reload:report` RBAC action."""

from ssm_server.access.policy import authorize
from ssm_server.access.scopes import DEFAULT_TOKEN_ACTION_SCOPES, global_scopes


def test_reload_report_is_enumerated_as_a_default_scope():
    assert "reload:report" in DEFAULT_TOKEN_ACTION_SCOPES


def test_default_token_is_authorized_to_report_reloads():
    actor = {"type": "token", "scopes": global_scopes()}
    assert authorize(actor, "reload:report", project_id="p1", config_id="c1")


def test_config_scoped_token_only_reports_for_its_config():
    actor = {
        "type": "token",
        "scopes": [
            {
                "project_id": "p1",
                "config_id": "c1",
                "actions": ["reload:report"],
            }
        ],
    }
    assert authorize(actor, "reload:report", project_id="p1", config_id="c1")
    assert not authorize(
        actor, "reload:report", project_id="p1", config_id="c2"
    )
