"""Unit tests for ``zehut user create``."""

from __future__ import annotations

import json

import pytest

from zehut import cli, users
from zehut.cli import _errors


@pytest.fixture
def tmp_zehut(tmp_path, monkeypatch):
    """Bootstrap zehut with default-backend=system. The harness patches out
    privilege checks and useradd so tests can freely create system-backed
    parents, which every sub-user test needs as a prerequisite.
    """
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 0)

    from zehut.backend import system as system_mod
    from zehut.backend.base import ProvisionResult

    monkeypatch.setattr(
        system_mod.SystemBackend,
        "provision",
        lambda self, *, name: ProvisionResult(system_user=name, system_uid=2000),
    )
    monkeypatch.setattr(system_mod.SystemBackend, "exists", lambda self, name: False)

    cli.main(["init", "--domain", "agents.example.com", "--default-backend", "system"])
    return config_dir, state_dir


def _make_parent(name: str = "parent") -> None:
    assert cli.main(["user", "create", name, "--system"]) == 0


def test_create_subuser_with_parent(tmp_zehut, capsys):
    _make_parent("agent")
    rc = cli.main(["user", "create", "alice", "--subuser", "--parent", "agent"])
    assert rc == 0
    rec = users.get("alice")
    assert rec.backend == "subuser"
    parent = users.get("agent")
    assert rec.parent_id == parent.id
    assert rec.email.endswith("@agents.example.com")


def test_create_subuser_without_parent_errors(tmp_zehut, capsys):
    rc = cli.main(["user", "create", "alice", "--subuser"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_USER_ERROR
    assert "--parent" in cap.err


def test_create_subuser_missing_parent_errors(tmp_zehut, capsys):
    rc = cli.main(["user", "create", "alice", "--subuser", "--parent", "ghost"])
    assert rc == _errors.EXIT_USER_ERROR


def test_create_subuser_with_subuser_parent_rejected(tmp_zehut, capsys):
    # Attempting to nest under a sub-user trips the "parent must be
    # system-backed" validator — which is the same constraint that
    # enforces the flat hierarchy. (A sub-user can only have a system
    # parent, and a system user can't have a parent, so by construction
    # sub-users can never own sub-users.)
    _make_parent("agent")
    assert cli.main(["user", "create", "bot1", "--subuser", "--parent", "agent"]) == 0
    rc = cli.main(["user", "create", "bot2", "--subuser", "--parent", "bot1"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_USER_ERROR
    assert "system-backed" in cap.err


def test_create_system_rejects_parent_flag(tmp_zehut, capsys):
    _make_parent("agent")
    rc = cli.main(["user", "create", "other", "--system", "--parent", "agent"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_USER_ERROR
    assert "--parent" in cap.err


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
    assert rec.parent_id is None


def test_create_system_without_root_errors(tmp_zehut, monkeypatch, capsys):
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 1000)
    rc = cli.main(["user", "create", "bob", "--system"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_PRIVILEGE
    assert "sudo" in cap.err


def test_create_duplicate_is_conflict(tmp_zehut, capsys):
    _make_parent("agent")
    cli.main(["user", "create", "alice", "--subuser", "--parent", "agent"])
    rc = cli.main(["user", "create", "alice", "--subuser", "--parent", "agent"])
    assert rc == _errors.EXIT_CONFLICT


def test_create_honours_configured_default(tmp_zehut, monkeypatch, capsys):
    # Default is already 'system' from the fixture; override to 'subuser'
    # and verify the default kicks in when the flag is omitted.
    _make_parent("agent")
    cli.main(["configuration", "set", "default_backend", "subuser"])
    rc = cli.main(["user", "create", "carol", "--parent", "agent"])
    assert rc == 0
    assert users.get("carol").backend == "subuser"


def test_create_json_output(tmp_zehut, capsys):
    _make_parent("agent")
    rc = cli.main(
        ["--json", "user", "create", "alice", "--subuser", "--parent", "agent", "--about", "qa"]
    )
    cap = capsys.readouterr()
    assert rc == 0
    payload = json.loads(cap.out.splitlines()[-1])
    assert payload["name"] == "alice"
    assert payload["about"] == "qa"
    assert payload["backend"] == "subuser"
    assert payload["parent_id"] is not None


def test_create_system_refuses_foreign_os_user(tmp_zehut, monkeypatch, capsys):
    """Existing OS user not managed by zehut must NOT be silently adopted."""
    from zehut.backend import system as system_mod

    # Pretend 'bob' already exists on the OS but not in our registry.
    monkeypatch.setattr(system_mod.SystemBackend, "exists", lambda self, name: name == "bob")
    rc = cli.main(["user", "create", "bob", "--system"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_CONFLICT
    assert "not zehut-managed" in cap.err or "refusing to adopt" in cap.err
