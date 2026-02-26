from Api.versioning import _read_pyproject_version


def test_read_pyproject_version_from_project_section(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[build-system]
requires = ["setuptools"]

[project]
name = "simple-secrets-manager"
version = "9.8.7"
""".strip(),
        encoding="utf-8",
    )
    assert _read_pyproject_version(pyproject) == "9.8.7"


def test_read_pyproject_version_returns_none_when_missing(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "ssm"\n', encoding="utf-8")
    assert _read_pyproject_version(pyproject) is None
