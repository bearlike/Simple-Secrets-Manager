from Access.policy import authorize


def test_scope_matching_config():
    actor = {
        "type": "token",
        "scopes": [
            {"project_id": "p1", "config_id": "c1", "actions": ["secrets:read"]},
            {"project_id": "p2", "actions": ["secrets:read"]},
        ],
    }
    assert authorize(actor, "secrets:read", project_id="p1", config_id="c1")
    assert not authorize(actor, "secrets:read", project_id="p1", config_id="c2")
    assert authorize(actor, "secrets:read", project_id="p2", config_id="c9")
