"""Concurrency and corruption-resilience tests for the ssm CLI storage layer.

These guard against the class of crash where multiple concurrent `ssm`
invocations share cache/config files. The historical bug: atomic writes
used a fixed temp filename derived from the target path, so concurrent
writers collided on that single temp file and the loser crashed with
FileNotFoundError at os.chmod/os.replace (and could leave a corrupt file
behind that then crashed readers with JSONDecodeError).
"""

from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path

import pytest

BASE = "http://localhost:8080/api"
PROJECT = "proj"
CONFIG = "conf"
DATA = {f"KEY_{i}": f"value_{i}" * 16 for i in range(32)}


def _cache_worker(cache_dir: str, iterations: int, err_q) -> None:
    import os

    os.environ["SSM_CACHE_DIR"] = cache_dir
    from ssm_cli.cache import load_secret_cache, save_secret_cache

    try:
        for _ in range(iterations):
            save_secret_cache(BASE, PROJECT, CONFIG, DATA)
            # Readers must never crash on a concurrently-updated file.
            load_secret_cache(BASE, PROJECT, CONFIG)
    except Exception as exc:  # noqa: BLE001 - surface any crash to parent
        err_q.put(f"{type(exc).__name__}: {exc}")


def _config_worker(config_file: str, iterations: int, err_q) -> None:
    import os

    os.environ["SSM_GLOBAL_CONFIG_FILE"] = config_file
    from ssm_cli.config import _atomic_write_json, _read_json, Path as _P

    path = _P(config_file)
    try:
        for _ in range(iterations):
            _atomic_write_json(path, {"base_url": BASE, "data": DATA})
            _read_json(path)
    except Exception as exc:  # noqa: BLE001
        err_q.put(f"{type(exc).__name__}: {exc}")


def _run_workers(target, arg, nproc=10, iterations=120):
    ctx = mp.get_context("fork")
    err_q = ctx.Queue()
    procs = [
        ctx.Process(target=target, args=(arg, iterations, err_q))
        for _ in range(nproc)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
    errors = []
    while not err_q.empty():
        errors.append(err_q.get())
    return errors


def test_save_secret_cache_survives_concurrent_processes(tmp_path):
    cache_dir = str(tmp_path / "cache")
    errors = _run_workers(_cache_worker, cache_dir)
    assert errors == [], f"concurrent cache writers crashed: {errors}"

    # Final file must be intact, valid JSON with the expected payload.
    from ssm_cli.cache import load_secret_cache

    import os

    os.environ["SSM_CACHE_DIR"] = cache_dir
    loaded = load_secret_cache(BASE, PROJECT, CONFIG)
    assert loaded == DATA


def test_atomic_write_json_survives_concurrent_processes(tmp_path):
    config_file = str(tmp_path / "config.json")
    errors = _run_workers(_config_worker, config_file)
    assert errors == [], f"concurrent config writers crashed: {errors}"

    # Final file must be valid JSON (not a half-written temp).
    text = Path(config_file).read_text(encoding="utf-8")
    json.loads(text)


def test_load_secret_cache_tolerates_corrupt_file(monkeypatch, tmp_path):
    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path))
    import hashlib

    from ssm_cli.cache import load_secret_cache

    digest = hashlib.sha256(
        f"{BASE}|{PROJECT}|{CONFIG}".encode("utf-8")
    ).hexdigest()
    path = tmp_path / "secrets" / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"fetched_at": 1, "dat', encoding="utf-8")  # truncated

    # Corrupt cache is treated as a miss, not a crash.
    assert load_secret_cache(BASE, PROJECT, CONFIG) is None


def test_read_json_tolerates_corrupt_file(tmp_path):
    from ssm_cli.config import _read_json

    path = tmp_path / "config.json"
    path.write_text('{"active_profile": "def', encoding="utf-8")  # truncated
    assert _read_json(path) == {}


def test_handle_errors_converts_oserror_to_clean_exit():
    import click

    from ssm_cli.main import _handle_errors

    @_handle_errors
    def boom():
        raise OSError("disk on fire")

    # Must become a clean click Exit, never an uncaught OSError traceback.
    with pytest.raises(click.exceptions.Exit):
        boom()


def test_handle_errors_preserves_click_exit_code():
    import click

    from ssm_cli.main import _handle_errors

    @_handle_errors
    def deliberate_exit():
        raise click.exceptions.Exit(7)

    with pytest.raises(click.exceptions.Exit) as excinfo:
        deliberate_exit()
    assert excinfo.value.exit_code == 7
