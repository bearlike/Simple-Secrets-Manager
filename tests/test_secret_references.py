from Api.resources.secrets.references import SecretReferenceError, SecretReferenceResolver


class _Fixture:
    def __init__(self):
        self.projects = {
            "app": {"_id": "p-app", "slug": "app"},
            "shared": {"_id": "p-shared", "slug": "shared"},
        }
        self.configs = {
            ("p-app", "dev"): {"_id": "c-dev", "slug": "dev"},
            ("p-app", "base"): {"_id": "c-base", "slug": "base"},
            ("p-shared", "prod"): {"_id": "c-shared-prod", "slug": "prod"},
        }
        self.exports = {
            "c-dev": {
                "USER": "brian",
                "PORT": "3030",
                "WEBSITE": "${USER}.doppler.com:${PORT}",
                "DB_URL": "postgres://${base.DB_USER}@db:5432/app",
                "SHARED_HOST": "${shared.prod.API_HOST}",
            },
            "c-base": {"DB_USER": "base_user"},
            "c-shared-prod": {"API_HOST": "api.example.com"},
        }
        self.scope_checks: list[tuple[str, str, str]] = []

    def get_project(self, slug: str):
        return self.projects.get(slug)

    def get_config(self, project_id, slug: str):
        return self.configs.get((project_id, slug))

    def export_config(self, config_id):
        payload = self.exports.get(config_id)
        if payload is None:
            return None, None, "Config not found", 404
        return dict(payload), None, "OK", 200

    def require_scope(self, action: str, project_id, config_id):
        self.scope_checks.append((action, str(project_id), str(config_id)))
        return None


def test_resolves_same_config_cross_config_and_cross_project_references():
    fixture = _Fixture()
    source = dict(fixture.exports["c-dev"])
    resolver = SecretReferenceResolver(
        project_slug="app",
        config_slug="dev",
        get_project_by_slug=fixture.get_project,
        get_config_by_slug=fixture.get_config,
        export_config=fixture.export_config,
        require_scope=fixture.require_scope,
        max_depth=8,
    )

    resolved = resolver.resolve_map(source)

    assert resolved["WEBSITE"] == "brian.doppler.com:3030"
    assert resolved["DB_URL"] == "postgres://base_user@db:5432/app"
    assert resolved["SHARED_HOST"] == "api.example.com"
    assert fixture.scope_checks == [
        ("secrets:read", "p-app", "c-base"),
        ("secrets:read", "p-shared", "c-shared-prod"),
    ]


def test_unresolved_references_render_as_empty_string():
    fixture = _Fixture()
    resolver = SecretReferenceResolver(
        project_slug="app",
        config_slug="dev",
        get_project_by_slug=fixture.get_project,
        get_config_by_slug=fixture.get_config,
        export_config=fixture.export_config,
        require_scope=fixture.require_scope,
        max_depth=8,
    )

    resolved = resolver.resolve_map({"A": "value-${MISSING}-suffix", "B": "${bad.token.with.extra.parts}"})
    assert resolved["A"] == "value--suffix"
    assert resolved["B"] == ""


def test_missing_context_reference_renders_empty_string():
    fixture = _Fixture()
    resolver = SecretReferenceResolver(
        project_slug="app",
        config_slug="dev",
        get_project_by_slug=fixture.get_project,
        get_config_by_slug=fixture.get_config,
        export_config=fixture.export_config,
        require_scope=fixture.require_scope,
        max_depth=8,
    )

    resolved = resolver.resolve_map({"A": "${missing.dev.API_HOST}", "B": "${app.missing.API_HOST}"})
    assert resolved["A"] == ""
    assert resolved["B"] == ""


def test_detects_reference_cycle():
    fixture = _Fixture()
    resolver = SecretReferenceResolver(
        project_slug="app",
        config_slug="dev",
        get_project_by_slug=fixture.get_project,
        get_config_by_slug=fixture.get_config,
        export_config=fixture.export_config,
        require_scope=fixture.require_scope,
        max_depth=8,
    )

    try:
        resolver.resolve_map({"A": "${B}", "B": "${A}"})
        raise AssertionError("Expected cycle detection failure")
    except SecretReferenceError as exc:
        assert "cycle" in exc.message.lower()


def test_enforces_max_depth_limit():
    fixture = _Fixture()
    resolver = SecretReferenceResolver(
        project_slug="app",
        config_slug="dev",
        get_project_by_slug=fixture.get_project,
        get_config_by_slug=fixture.get_config,
        export_config=fixture.export_config,
        require_scope=fixture.require_scope,
        max_depth=1,
    )

    try:
        resolver.resolve_map({"A": "${B}", "B": "${C}", "C": "ok"})
        raise AssertionError("Expected depth error")
    except SecretReferenceError as exc:
        assert "max depth" in exc.message.lower()


def test_validate_value_references_fails_for_unresolved_and_invalid_tokens():
    fixture = _Fixture()
    resolver = SecretReferenceResolver(
        project_slug="app",
        config_slug="dev",
        get_project_by_slug=fixture.get_project,
        get_config_by_slug=fixture.get_config,
        export_config=fixture.export_config,
        require_scope=fixture.require_scope,
        max_depth=8,
        root_data=dict(fixture.exports["c-dev"]),
    )

    errors = resolver.validate_value_references(key="BROKEN", value="${missing.dev.API_HOST}:${bad-token}")
    assert any("Unresolved reference" in item for item in errors)
    assert any("Invalid reference syntax" in item for item in errors)


def test_validate_value_references_detects_nested_broken_reference():
    fixture = _Fixture()
    fixture.exports["c-base"]["BROKEN"] = "${doesnotexist.KEY}"
    root_data = dict(fixture.exports["c-dev"])
    root_data["DATABASE_URL"] = "postgres://${base.BROKEN}@db:5432/app"
    resolver = SecretReferenceResolver(
        project_slug="app",
        config_slug="dev",
        get_project_by_slug=fixture.get_project,
        get_config_by_slug=fixture.get_config,
        export_config=fixture.export_config,
        require_scope=fixture.require_scope,
        max_depth=8,
        root_data=root_data,
    )

    errors = resolver.validate_value_references(key="DATABASE_URL", value=root_data["DATABASE_URL"])
    assert any("Unresolved reference" in item for item in errors)
