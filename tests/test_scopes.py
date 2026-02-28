from Access.policy import authorize


def test_scope_matching_config():
    actor = {
        "type": "token",
        "scopes": [
            {
                "project_id": "p1",
                "config_id": "c1",
                "actions": ["secrets:read"],
            },
            {"project_id": "p2", "actions": ["secrets:read"]},
        ],
    }
    assert authorize(actor, "secrets:read", project_id="p1", config_id="c1")
    assert not authorize(
        actor, "secrets:read", project_id="p1", config_id="c2"
    )
    assert authorize(actor, "secrets:read", project_id="p2", config_id="c9")


def test_global_scope_matches_project_and_config_requests():
    actor = {
        "type": "token",
        "scopes": [
            {"actions": ["configs:read", "configs:write"]},
        ],
    }
    assert authorize(actor, "configs:read", project_id="p1")
    assert authorize(actor, "configs:write", project_id="p1", config_id="c1")


def test_userpass_actor_is_not_auto_authorized():
    actor = {"type": "userpass", "id": "alice"}
    assert not authorize(actor, "projects:read")


def test_personal_token_scopes_are_intersection_of_dynamic_and_token_scopes():
    actor = {
        "type": "token",
        "token_type": "personal",
        "scopes": [{"project_id": "p1", "actions": ["secrets:write"]}],
        "token_scopes": [{"project_id": "p1", "actions": ["secrets:read"]}],
    }
    assert not authorize(actor, "secrets:write", project_id="p1")
    assert not authorize(actor, "secrets:read", project_id="p1")

    actor["token_scopes"] = [
        {"project_id": "p1", "actions": ["secrets:write"]}
    ]
    assert authorize(actor, "secrets:write", project_id="p1")
