"""Unit tests for ``zehut configuration ...``."""

from __future__ import annotations

import json

import pytest

from zehut import cli, config
from zehut.cli import _errors


@pytest.fixture
def tmp_zehut(tmp_path, monkeypatch):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 0)
    cli.main(["init", "--domain", "old.example.com", "--default-backend", "subuser"])
    return config_dir, state_dir


def test_configuration_show_json(tmp_zehut, capsys):
    rc = cli.main(["--json", "configuration", "show"])
    cap = capsys.readouterr()
    assert rc == 0
    payload = json.loads(cap.out.splitlines()[-1])
    assert payload["domain"] == "old.example.com"
    assert payload["schema_version"] == 1


def test_configuration_show_text(tmp_zehut, capsys):
    rc = cli.main(["configuration", "show"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "old.example.com" in cap.out


def test_configuration_set_domain(tmp_zehut, capsys):
    rc = cli.main(["configuration", "set-domain", "new.example.com"])
    assert rc == 0
    assert config.load().domain == "new.example.com"


def test_configuration_set_generic(tmp_zehut, capsys):
    rc = cli.main(["configuration", "set", "default_backend", "system"])
    assert rc == 0
    assert config.load().default_backend == "system"


def test_configuration_set_rejects_unknown_key(tmp_zehut, capsys):
    rc = cli.main(["configuration", "set", "frobnicate", "no"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_STATE
    assert (
        "unknown" in cap.err.lower()
        or "settable" in cap.err.lower()
        or "invalid" in cap.err.lower()
    )


def test_configuration_set_requires_root(tmp_zehut, monkeypatch, capsys):
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 1000)
    rc = cli.main(["configuration", "set-domain", "nope.com"])
    capsys.readouterr()
    assert rc == _errors.EXIT_PRIVILEGE
