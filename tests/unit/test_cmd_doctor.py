"""Unit tests for ``zehut doctor``."""

from __future__ import annotations

import json

import pytest

from zehut import cli


@pytest.fixture
def tmp_zehut(tmp_path, monkeypatch):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 0)
    return config_dir, state_dir


def test_doctor_fails_when_uninitialised(tmp_zehut, capsys):
    rc = cli.main(["--json", "doctor"])
    cap = capsys.readouterr()
    payload = json.loads(cap.out.splitlines()[-1])
    # Expect a FAIL on config-exists check.
    check_names = {c["name"]: c["status"] for c in payload["checks"]}
    assert check_names["config_exists"] == "FAIL"
    # doctor itself exits 0 — it's a report.
    assert rc == 0


def test_doctor_all_pass_after_init(tmp_zehut, capsys):
    cli.main(["init", "--domain", "agents.example.com", "--default-backend", "subuser"])
    rc = cli.main(["--json", "doctor"])
    cap = capsys.readouterr()
    payload = json.loads(cap.out.splitlines()[-1])
    statuses = {c["status"] for c in payload["checks"]}
    assert "FAIL" not in statuses
    assert rc == 0


def test_doctor_reports_drift_when_system_entry_has_unknown_uid(tmp_zehut, monkeypatch, capsys):
    cli.main(["init", "--domain", "agents.example.com", "--default-backend", "subuser"])
    from zehut.backend import system as system_mod
    from zehut.backend.base import ProvisionResult

    monkeypatch.setattr(
        system_mod.SystemBackend,
        "provision",
        lambda self, *, name: ProvisionResult(system_user=name, system_uid=5001),
    )
    cli.main(["user", "create", "bob", "--system"])

    # Now pretend bob is gone from /etc/passwd.
    import pwd as _pwd

    def _getpwnam(name):
        raise KeyError(name)

    monkeypatch.setattr(_pwd, "getpwnam", _getpwnam)
    rc = cli.main(["--json", "doctor"])
    cap = capsys.readouterr()
    payload = json.loads(cap.out.splitlines()[-1])
    names = {c["name"]: c["status"] for c in payload["checks"]}
    assert names["system_users_resolve"] == "FAIL"
    assert rc == 0
