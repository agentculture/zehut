"""Unit tests for zehut.backend.system — all subprocess calls mocked."""

from __future__ import annotations

import subprocess
import types

import pytest

from zehut.backend import system
from zehut.backend.base import ProvisionResult
from zehut.cli._errors import EXIT_BACKEND, EXIT_USER_ERROR, ZehutError


@pytest.fixture
def fake_pwd(monkeypatch):
    """Install a fake ``pwd.getpwnam`` that returns a predictable record."""
    entries: dict[str, int] = {}

    def _getpwnam(name: str):
        if name not in entries:
            raise KeyError(name)
        return types.SimpleNamespace(pw_name=name, pw_uid=entries[name])

    monkeypatch.setattr(system.pwd, "getpwnam", _getpwnam)
    return entries


@pytest.fixture
def fake_run(monkeypatch):
    """Record subprocess.run calls and simulate success."""
    calls: list[list[str]] = []

    def _run(args, *, check, env, stdout, stderr):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(system.subprocess, "run", _run)
    return calls


def test_provision_rejects_bad_name(fake_pwd, fake_run):
    be = system.SystemBackend()
    with pytest.raises(ZehutError) as exc:
        be.provision(name="WithCaps")
    assert exc.value.code == EXIT_USER_ERROR
    assert "name" in exc.value.message.lower()


def test_provision_calls_useradd_with_expected_flags(fake_pwd, fake_run):
    fake_pwd["alice"] = 1001
    be = system.SystemBackend()
    result = be.provision(name="alice")
    assert isinstance(result, ProvisionResult)
    assert result.system_user == "alice"
    assert result.system_uid == 1001
    assert fake_run == [["useradd", "-m", "-U", "-s", "/bin/bash", "alice"]]


def test_provision_pins_path(monkeypatch, fake_pwd):
    """useradd must be invoked with PATH = /usr/sbin:/usr/bin."""
    seen_env: dict[str, str] = {}

    def _run(args, *, check, env, stdout, stderr):
        seen_env.update(env or {})
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(system.subprocess, "run", _run)
    fake_pwd["alice"] = 1001
    system.SystemBackend().provision(name="alice")
    assert seen_env.get("PATH") == "/usr/sbin:/usr/bin"


def test_provision_raises_backend_on_nonzero_useradd(monkeypatch, fake_pwd):
    def _run(args, *, check, env, stdout, stderr):
        return subprocess.CompletedProcess(args, 9, b"", b"useradd: user 'alice' already exists\n")

    monkeypatch.setattr(system.subprocess, "run", _run)
    be = system.SystemBackend()
    with pytest.raises(ZehutError) as exc:
        be.provision(name="alice")
    assert exc.value.code == EXIT_BACKEND
    assert "useradd" in exc.value.message.lower()


def test_deprovision_calls_userdel_with_dash_r_by_default(fake_run):
    system.SystemBackend().deprovision(name="alice", system_user="alice", keep_home=False)
    assert fake_run == [["userdel", "-r", "alice"]]


def test_deprovision_keep_home_drops_dash_r(fake_run):
    system.SystemBackend().deprovision(name="alice", system_user="alice", keep_home=True)
    assert fake_run == [["userdel", "alice"]]


def test_deprovision_raises_backend_on_nonzero_userdel(monkeypatch):
    def _run(args, *, check, env, stdout, stderr):
        return subprocess.CompletedProcess(args, 6, b"", b"userdel: user 'alice' does not exist\n")

    monkeypatch.setattr(system.subprocess, "run", _run)
    with pytest.raises(ZehutError) as exc:
        system.SystemBackend().deprovision(name="alice", system_user="alice", keep_home=False)
    assert exc.value.code == EXIT_BACKEND


def test_exists_consults_pwd(fake_pwd):
    fake_pwd["alice"] = 1001
    be = system.SystemBackend()
    assert be.exists("alice") is True
    assert be.exists("ghost") is False
