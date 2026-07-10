"""The directory sink: where a rendered config lands, and how safely."""

from __future__ import annotations

import stat
from pathlib import Path

from ssm_projection import DirectorySink, env_filename


def test_env_filename_is_the_project_config_pair() -> None:
    assert env_filename("vpn", "zurich") == "vpn-zurich.env"


def test_write_creates_the_file_with_owner_group_read_only_mode(
    tmp_path: Path,
) -> None:
    sink = DirectorySink(tmp_path / "run" / "ssm")

    target = sink.write("vpn", "zurich", {"WIREGUARD_DNS": "10.2.0.1"})

    assert Path(target).read_text() == 'WIREGUARD_DNS="10.2.0.1"\n'
    mode = stat.S_IMODE(Path(target).stat().st_mode)
    # 0640: the consuming container reads it as a group member; nobody else
    # on the host can. World-readable secrets would defeat the tmpfs volume.
    assert oct(mode) == "0o640"


def test_write_is_atomic_and_leaves_no_temp_file_behind(
    tmp_path: Path,
) -> None:
    sink = DirectorySink(tmp_path)
    sink.write("vpn", "zurich", {"A": "1"})

    sink.write("vpn", "zurich", {"A": "2"})

    assert [p.name for p in tmp_path.iterdir()] == ["vpn-zurich.env"]
    assert (tmp_path / "vpn-zurich.env").read_text() == 'A="2"\n'


def test_exists_reports_whether_the_config_has_been_projected(
    tmp_path: Path,
) -> None:
    sink = DirectorySink(tmp_path)

    assert sink.exists("vpn", "zurich") is False

    sink.write("vpn", "zurich", {"A": "1"})

    assert sink.exists("vpn", "zurich") is True
