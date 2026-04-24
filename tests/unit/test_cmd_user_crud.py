"""Unit tests for ``zehut user list|show|set|delete``."""

from __future__ import annotations

import json

import pytest

from zehut import cli, users
from zehut.cli import _errors


@pytest.fixture
def tmp_zehut_with_alice(tmp_path, monkeypatch):
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
    monkeypatch.setattr(
        system_mod.SystemBackend,
        "deprovision",
        lambda self, *, name, system_user, keep_home: None,
    )
    monkeypatch.setattr(system_mod.SystemBackend, "exists", lambda self, name: False)

    cli.main(["init", "--domain", "agents.example.com", "--default-backend", "system"])
    # Parent (system) + sub-user alice.
    cli.main(["user", "create", "agent", "--system"])
    cli.main(
        [
            "user",
            "create",
            "alice",
            "--subuser",
            "--parent",
            "agent",
            "--nick",
            "Ali",
            "--about",
            "qa",
        ]
    )
    return config_dir, state_dir


def test_list_json(tmp_zehut_with_alice, capsys):
    rc = cli.main(["--json", "user", "list"])
    cap = capsys.readouterr()
    assert rc == 0
    payload = json.loads(cap.out.splitlines()[-1])
    assert isinstance(payload, list)
    names = {p["name"] for p in payload}
    assert names == {"agent", "alice"}


def test_list_text(tmp_zehut_with_alice, capsys):
    rc = cli.main(["user", "list"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "alice" in cap.out
    assert "subuser" in cap.out
    assert "agent" in cap.out  # parent column for alice resolves to agent


def test_show_by_name(tmp_zehut_with_alice, capsys):
    rc = cli.main(["user", "show", "alice"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "alice" in cap.out
    assert "Ali" in cap.out


def test_show_unknown_user(tmp_zehut_with_alice, capsys):
    rc = cli.main(["user", "show", "ghost"])
    assert rc == _errors.EXIT_USER_ERROR


def test_set_nick_by_name(tmp_zehut_with_alice, capsys):
    rc = cli.main(["user", "set", "alice", "nick=Alicia"])
    assert rc == 0
    assert users.get("alice").nick == "Alicia"


def test_set_multiple_fields(tmp_zehut_with_alice, capsys):
    rc = cli.main(["user", "set", "alice", "nick=A", "about=new"])
    assert rc == 0
    rec = users.get("alice")
    assert rec.nick == "A"
    assert rec.about == "new"


def test_set_rejects_unknown_key(tmp_zehut_with_alice, capsys):
    rc = cli.main(["user", "set", "alice", "email=other@x.com"])
    assert rc == _errors.EXIT_USER_ERROR


def test_set_bad_assignment_syntax(tmp_zehut_with_alice, capsys):
    rc = cli.main(["user", "set", "alice", "nick Alicia"])
    assert rc == _errors.EXIT_USER_ERROR


def test_delete_subuser_no_root_needed(tmp_zehut_with_alice, monkeypatch, capsys):
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 1000)
    rc = cli.main(["user", "delete", "alice"])
    assert rc == 0
    remaining = {r.name for r in users.list_all()}
    assert remaining == {"agent"}


def test_delete_subuser_reports_no_cascade(tmp_zehut_with_alice, capsys):
    rc = cli.main(["--json", "user", "delete", "alice"])
    cap = capsys.readouterr()
    assert rc == 0
    payload = json.loads(cap.out.splitlines()[-1])
    assert payload == {"deleted": "alice", "backend": "subuser", "cascaded_subusers": []}


def test_delete_parent_cascades_to_subusers(tmp_zehut_with_alice, capsys):
    # Add a second sub-user under agent to prove both get cascaded.
    assert cli.main(["user", "create", "bot2", "--subuser", "--parent", "agent"]) == 0
    rc = cli.main(["--json", "user", "delete", "agent"])
    cap = capsys.readouterr()
    assert rc == 0
    payload = json.loads(cap.out.splitlines()[-1])
    assert payload["deleted"] == "agent"
    assert payload["backend"] == "system"
    assert sorted(payload["cascaded_subusers"]) == ["alice", "bot2"]
    assert users.list_all() == []


def test_delete_system_needs_root(tmp_path, monkeypatch, capsys):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 0)
    cli.main(["init", "--domain", "agents.example.com", "--default-backend", "system"])

    from zehut.backend import system as system_mod
    from zehut.backend.base import ProvisionResult

    monkeypatch.setattr(
        system_mod.SystemBackend,
        "provision",
        lambda self, *, name: ProvisionResult(system_user=name, system_uid=3001),
    )
    monkeypatch.setattr(
        system_mod.SystemBackend,
        "deprovision",
        lambda self, *, name, system_user, keep_home: None,
    )
    cli.main(["user", "create", "bob", "--system"])

    # Drop root for the delete.
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 1000)
    rc = cli.main(["user", "delete", "bob"])
    assert rc == _errors.EXIT_PRIVILEGE


def test_set_ambient_via_env_identity(tmp_zehut_with_alice, monkeypatch, capsys):
    """`zehut user set nick=X` should resolve ambient via $ZEHUT_IDENTITY."""
    monkeypatch.setenv("ZEHUT_IDENTITY", "alice")
    rc = cli.main(["user", "set", "nick=Alicia"])
    assert rc == 0
    assert users.get("alice").nick == "Alicia"
