"""Unit tests for ``zehut user switch`` / ``whoami`` / ``current``."""

from __future__ import annotations

import json

import pytest

from zehut import cli
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

    from zehut.backend import system as system_mod
    from zehut.backend.base import ProvisionResult

    monkeypatch.setattr(
        system_mod.SystemBackend,
        "provision",
        lambda self, *, name: ProvisionResult(system_user=name, system_uid=2000),
    )
    monkeypatch.setattr(system_mod.SystemBackend, "exists", lambda self, name: False)

    cli.main(["init", "--domain", "agents.example.com", "--default-backend", "system"])
    # Seed a parent that sub-user tests can hang off.
    cli.main(["user", "create", "agent", "--system"])
    return config_dir, state_dir


def _make_subuser(name: str, parent: str = "agent") -> None:
    assert cli.main(["user", "create", name, "--subuser", "--parent", parent]) == 0


def test_switch_subuser_prints_export(tmp_zehut, capsys):
    _make_subuser("alice")
    capsys.readouterr()  # flush create output
    rc = cli.main(["user", "switch", "alice"])
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out.strip() == "export ZEHUT_IDENTITY=alice"


def test_switch_unknown_user(tmp_zehut, capsys):
    rc = cli.main(["user", "switch", "ghost"])
    assert rc == _errors.EXIT_USER_ERROR


def test_switch_system_execs_sudo(tmp_zehut, monkeypatch, capsys):
    recorded: list[list[str]] = []

    def fake_execv(prog, argv):
        recorded.append([prog, *argv[1:]])
        raise SystemExit(0)

    # The command now uses a hardcoded trusted path list (/usr/bin/sudo
    # then /bin/sudo). Make the first candidate look present and executable.
    import os as _os

    real_isfile = _os.path.isfile
    real_access = _os.access
    monkeypatch.setattr(
        _os.path, "isfile", lambda p: True if p == "/usr/bin/sudo" else real_isfile(p)
    )
    monkeypatch.setattr(
        _os,
        "access",
        lambda p, mode: True if p == "/usr/bin/sudo" else real_access(p, mode),
    )
    monkeypatch.setattr("os.execv", fake_execv)

    # main() no longer catches SystemExit (removed to clear Sonar S5754);
    # os.execv in production replaces the process and never returns, so the
    # test's SystemExit-raising mock accurately represents that contract.
    with pytest.raises(SystemExit) as excinfo:
        # Switch to the seeded 'agent' system user.
        cli.main(["user", "switch", "agent"])
    assert excinfo.value.code == 0
    assert recorded == [["/usr/bin/sudo", "-u", "agent", "-i"]]


def test_whoami_none_when_no_ambient(tmp_zehut, monkeypatch, capsys):
    monkeypatch.delenv("ZEHUT_IDENTITY", raising=False)
    # The seeded 'agent' would resolve ambient via getpwuid if the test
    # happens to run as a user literally named 'agent'. Guard by patching.
    import types

    monkeypatch.setattr(
        "zehut.users.pwd.getpwuid",
        lambda uid: types.SimpleNamespace(pw_name="nobody", pw_uid=65534),
    )
    rc = cli.main(["user", "whoami"])
    assert rc == _errors.EXIT_USER_ERROR


def test_whoami_env_fallback(tmp_zehut, monkeypatch, capsys):
    _make_subuser("alice")
    monkeypatch.setenv("ZEHUT_IDENTITY", "alice")
    rc = cli.main(["user", "whoami"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "alice" in cap.out


def test_whoami_json(tmp_zehut, monkeypatch, capsys):
    _make_subuser("alice")
    monkeypatch.setenv("ZEHUT_IDENTITY", "alice")
    assert cli.main(["--json", "user", "whoami"]) == 0
    cap = capsys.readouterr()
    payload = json.loads(cap.out.splitlines()[-1])
    assert payload["name"] == "alice"


def test_current_is_an_alias_for_whoami(tmp_zehut, monkeypatch, capsys):
    _make_subuser("alice")
    monkeypatch.setenv("ZEHUT_IDENTITY", "alice")
    rc = cli.main(["user", "current"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "alice" in cap.out
