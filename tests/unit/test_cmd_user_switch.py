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
    cli.main(["init", "--domain", "agents.example.com", "--default-backend", "logical"])
    return config_dir, state_dir


def test_switch_logical_prints_export(tmp_zehut, capsys):
    cli.main(["user", "create", "alice"])
    capsys.readouterr()  # flush create output
    rc = cli.main(["user", "switch", "alice"])
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out.strip() == "export ZEHUT_IDENTITY=alice"


def test_switch_unknown_user(tmp_zehut, capsys):
    rc = cli.main(["user", "switch", "ghost"])
    assert rc == _errors.EXIT_USER_ERROR


def test_switch_system_execs_sudo(tmp_zehut, monkeypatch, capsys):
    from zehut.backend import system as system_mod
    from zehut.backend.base import ProvisionResult

    monkeypatch.setattr(
        system_mod.SystemBackend,
        "provision",
        lambda self, *, name: ProvisionResult(system_user=name, system_uid=4001),
    )
    cli.main(["user", "create", "bob", "--system"])

    recorded: list[list[str]] = []

    def fake_execvp(prog, argv):
        recorded.append([prog, *argv[1:]])
        raise SystemExit(0)

    monkeypatch.setattr("os.execvp", fake_execvp)
    rc = cli.main(["user", "switch", "bob"])
    # The test harness's main() catches SystemExit and returns the code as int.
    assert rc == 0
    assert recorded == [["sudo", "-u", "bob", "-i"]]


def test_whoami_none_when_no_ambient(tmp_zehut, monkeypatch, capsys):
    monkeypatch.delenv("ZEHUT_IDENTITY", raising=False)
    rc = cli.main(["user", "whoami"])
    assert rc == _errors.EXIT_USER_ERROR


def test_whoami_env_fallback(tmp_zehut, monkeypatch, capsys):
    cli.main(["user", "create", "alice"])
    monkeypatch.setenv("ZEHUT_IDENTITY", "alice")
    rc = cli.main(["user", "whoami"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "alice" in cap.out


def test_whoami_json(tmp_zehut, monkeypatch, capsys):
    cli.main(["user", "create", "alice"])
    monkeypatch.setenv("ZEHUT_IDENTITY", "alice")
    assert cli.main(["--json", "user", "whoami"]) == 0
    cap = capsys.readouterr()
    payload = json.loads(cap.out.splitlines()[-1])
    assert payload["name"] == "alice"


def test_current_is_an_alias_for_whoami(tmp_zehut, monkeypatch, capsys):
    cli.main(["user", "create", "alice"])
    monkeypatch.setenv("ZEHUT_IDENTITY", "alice")
    rc = cli.main(["user", "current"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "alice" in cap.out
