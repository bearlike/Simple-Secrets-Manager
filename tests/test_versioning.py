from Engines.versioning import read_version_file


def test_read_version_file_returns_value(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("9.8.7\n", encoding="utf-8")
    assert read_version_file(version_file) == "9.8.7"


def test_read_version_file_returns_none_when_missing(tmp_path):
    missing_file = tmp_path / "MISSING_VERSION"
    assert read_version_file(missing_file) is None
