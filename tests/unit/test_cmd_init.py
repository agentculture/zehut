"""Unit tests for ``zehut init``."""

from __future__ import annotations

import json

import pytest

from zehut import cli, config, users
from zehut.cli import _errors


@pytest.fixture
def tmp_zehut(tmp_path, monkeypatch):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    # Pretend we are root for these tests.
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 0)
    return config_dir, state_dir


def test_init_non_interactive_writes_both_files(tmp_zehut, capsys):
    rc = cli.main(["init", "--domain", "agents.example.com", "--default-backend", "system"])
    assert rc == 0
    cfg = config.load()
    assert cfg.domain == "agents.example.com"
    assert cfg.default_backend == "system"
    assert users.list_all() == []


def test_init_refuses_when_not_root(tmp_zehut, monkeypatch, capsys):
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 1000)
    rc = cli.main(["init", "--domain", "x.com", "--default-backend", "logical"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_PRIVILEGE
    assert "sudo" in cap.err


def test_init_is_idempotent_without_force(tmp_zehut, capsys):
    cli.main(["init", "--domain", "x.com", "--default-backend", "logical"])
    rc = cli.main(["init", "--domain", "ignored.com", "--default-backend", "system"])
    assert rc == 0
    assert config.load().domain == "x.com"  # unchanged


def test_init_force_overwrites(tmp_zehut, capsys):
    cli.main(["init", "--domain", "x.com", "--default-backend", "logical"])
    rc = cli.main(
        [
            "init",
            "--force",
            "--domain",
            "new.com",
            "--default-backend",
            "system",
        ]
    )
    assert rc == 0
    assert config.load().domain == "new.com"


def test_init_json_output(tmp_zehut, capsys):
    rc = cli.main(
        [
            "--json",
            "init",
            "--domain",
            "agents.example.com",
            "--default-backend",
            "system",
        ]
    )
    assert rc == 0
    cap = capsys.readouterr()
    payload = json.loads(cap.out.splitlines()[-1])
    assert payload["domain"] == "agents.example.com"
    assert payload["default_backend"] == "system"
    assert payload["initialised"] is True
