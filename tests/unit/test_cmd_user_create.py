"""Unit tests for ``zehut user create``."""

from __future__ import annotations

import json

import pytest

from zehut import cli, users
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
    cli.main(["init", "--domain", "agents.example.com", "--default-backend", "logical"])
    return config_dir, state_dir


def test_create_logical_default(tmp_zehut, capsys):
    rc = cli.main(["user", "create", "alice"])
    assert rc == 0
    recs = users.list_all()
    assert len(recs) == 1
    assert recs[0].name == "alice"
    assert recs[0].backend == "logical"
    assert recs[0].email.endswith("@agents.example.com")


def test_create_with_explicit_system_flag(tmp_zehut, monkeypatch, capsys):
    from zehut.backend import system as system_mod
    from zehut.backend.base import ProvisionResult

    monkeypatch.setattr(
        system_mod.SystemBackend,
        "provision",
        lambda self, *, name: ProvisionResult(system_user=name, system_uid=2001),
    )
    rc = cli.main(["user", "create", "bob", "--system", "--nick", "Bobby"])
    assert rc == 0
    rec = users.get("bob")
    assert rec.backend == "system"
    assert rec.nick == "Bobby"
    assert rec.system_uid == 2001


def test_create_system_without_root_errors(tmp_zehut, monkeypatch, capsys):
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 1000)
    rc = cli.main(["user", "create", "bob", "--system"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_PRIVILEGE
    assert "sudo" in cap.err


def test_create_duplicate_is_conflict(tmp_zehut, capsys):
    cli.main(["user", "create", "alice"])
    rc = cli.main(["user", "create", "alice"])
    assert rc == _errors.EXIT_CONFLICT


def test_create_honours_configured_default(tmp_zehut, monkeypatch, capsys):
    from zehut.backend import system as system_mod
    from zehut.backend.base import ProvisionResult

    monkeypatch.setattr(
        system_mod.SystemBackend,
        "provision",
        lambda self, *, name: ProvisionResult(system_user=name, system_uid=2002),
    )
    # Flip default to system.
    cli.main(["configuration", "set", "default_backend", "system"])
    rc = cli.main(["user", "create", "carol"])
    assert rc == 0
    assert users.get("carol").backend == "system"


def test_create_json_output(tmp_zehut, capsys):
    rc = cli.main(["--json", "user", "create", "alice", "--about", "qa"])
    cap = capsys.readouterr()
    assert rc == 0
    payload = json.loads(cap.out.splitlines()[-1])
    assert payload["name"] == "alice"
    assert payload["about"] == "qa"
    assert payload["backend"] == "logical"
