"""The reloader's projection layer — delivery, as opposed to convergence."""

from __future__ import annotations

from pathlib import Path

from ssm_projection import DirectorySink
from ssm_reload.models import ConfigRef
from ssm_reload.projection import Projector
from tests.reload.conftest import FakeSink

ZURICH = ConfigRef("vpn", "zurich")


def test_needs_render_is_true_until_the_file_exists() -> None:
    projector = Projector(FakeSink())

    assert projector.needs_render(ZURICH) is True

    assert projector.render(ZURICH, {"K": "v"}, '"v1"') is None

    assert projector.needs_render(ZURICH) is False


def test_render_remembers_the_revision_for_containerless_configs() -> None:
    # A config nothing is bound to has no container label to read a held
    # revision from, so the projector's own memory restores the 304 path.
    projector = Projector(FakeSink())

    assert projector.last_revision(ZURICH) is None

    projector.render(ZURICH, {"K": "v"}, '"v2"')

    assert projector.last_revision(ZURICH) == '"v2"'


def test_a_failing_sink_is_returned_as_an_error_never_raised(caplog) -> None:
    # Swallowing it would leave the reloader reporting a green fleet view over
    # a config whose env_file was never written; raising would take the
    # containers that still need a recreate down with it. So: return it.
    projector = Projector(FakeSink(fail=OSError("read-only file system")))

    with caplog.at_level("WARNING"):
        error = projector.render(ZURICH, {"K": "v"}, '"v1"')

    assert error is not None
    assert "read-only file system" in error
    assert "read-only file system" in caplog.text
    # Still needs a render: the next pass retries rather than pretending the
    # file is on disk.
    assert projector.needs_render(ZURICH) is True


def test_render_writes_a_real_dotenv_file_through_the_directory_sink(
    tmp_path: Path,
) -> None:
    projector = Projector(DirectorySink(tmp_path))

    projector.render(ZURICH, {"WIREGUARD_DNS": "10.2.0.1"}, '"v1"')

    assert (tmp_path / "vpn-zurich.env").read_text() == (
        'WIREGUARD_DNS="10.2.0.1"\n'
    )


def test_a_bad_key_name_stops_the_write_for_that_config_only(
    tmp_path: Path, caplog
) -> None:
    # An unrenderable key would produce a file compose cannot parse; refuse to
    # write it rather than break the operator's whole stack.
    projector = Projector(DirectorySink(tmp_path))

    with caplog.at_level("WARNING"):
        error = projector.render(ZURICH, {"a-b": "v"}, '"v1"')

    assert error is not None
    assert list(tmp_path.iterdir()) == []
