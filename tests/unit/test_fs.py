"""Unit tests for zehut.fs — paths, locking, atomic writes."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from zehut import fs


@pytest.fixture
def tmp_zehut(tmp_path, monkeypatch):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    return config_dir, state_dir


def test_default_paths_without_env(monkeypatch):
    monkeypatch.delenv("ZEHUT_CONFIG_DIR", raising=False)
    monkeypatch.delenv("ZEHUT_STATE_DIR", raising=False)
    assert fs.config_dir() == Path("/etc/zehut")
    assert fs.state_dir() == Path("/var/lib/zehut")
    assert fs.config_file() == Path("/etc/zehut/config.toml")
    assert fs.users_file() == Path("/var/lib/zehut/users.json")
    assert fs.lock_file() == Path("/var/lib/zehut/.lock")


def test_paths_honour_env_overrides(tmp_zehut):
    config_dir, state_dir = tmp_zehut
    assert fs.config_dir() == config_dir
    assert fs.state_dir() == state_dir
    assert fs.config_file() == config_dir / "config.toml"
    assert fs.users_file() == state_dir / "users.json"


def test_atomic_write_text_creates_file_with_content(tmp_zehut):
    _, state_dir = tmp_zehut
    target = state_dir / "x.txt"
    fs.atomic_write_text(target, "hello\n", mode=0o644)
    assert target.read_text() == "hello\n"
    assert oct(target.stat().st_mode & 0o777) == oct(0o644)


def test_atomic_write_text_overwrites(tmp_zehut):
    _, state_dir = tmp_zehut
    target = state_dir / "x.txt"
    target.write_text("old")
    fs.atomic_write_text(target, "new", mode=0o644)
    assert target.read_text() == "new"


def test_atomic_write_text_leaves_no_tmp_on_success(tmp_zehut):
    _, state_dir = tmp_zehut
    target = state_dir / "x.txt"
    fs.atomic_write_text(target, "ok", mode=0o644)
    tmps = [p for p in state_dir.iterdir() if p.name.startswith(".x.txt.")]
    assert tmps == []


def test_exclusive_lock_blocks_concurrent_writer(tmp_zehut):
    _, state_dir = tmp_zehut
    lock_path = state_dir / ".lock"
    lock_path.touch()
    observed: list[str] = []

    def worker(tag: str, hold_for: float):
        import time

        with fs.exclusive_lock(lock_path):
            observed.append(f"{tag}-enter")
            time.sleep(hold_for)
            observed.append(f"{tag}-leave")

    t1 = threading.Thread(target=worker, args=("a", 0.2))
    t2 = threading.Thread(target=worker, args=("b", 0.0))
    t1.start()
    # give t1 time to acquire the lock before t2 races
    import time as _time

    _time.sleep(0.05)
    t2.start()
    t1.join()
    t2.join()

    # a must fully enter and leave before b enters
    assert observed == ["a-enter", "a-leave", "b-enter", "b-leave"]


def test_read_json_roundtrip(tmp_zehut):
    _, state_dir = tmp_zehut
    target = state_dir / "data.json"
    payload = {"schema_version": 1, "users": []}
    fs.atomic_write_text(target, json.dumps(payload), mode=0o644)
    assert fs.read_json(target) == payload


def test_read_json_missing_raises_filenotfound(tmp_zehut):
    _, state_dir = tmp_zehut
    with pytest.raises(FileNotFoundError):
        fs.read_json(state_dir / "nope.json")
