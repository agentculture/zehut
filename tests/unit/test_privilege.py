"""Unit tests for zehut.privilege."""

from __future__ import annotations

import pytest

from zehut import privilege


def test_is_root_true(monkeypatch):
    monkeypatch.setattr(privilege.os, "geteuid", lambda: 0)
    assert privilege.is_root() is True


def test_is_root_false(monkeypatch):
    monkeypatch.setattr(privilege.os, "geteuid", lambda: 1000)
    assert privilege.is_root() is False


def test_require_root_passes_when_root(monkeypatch):
    monkeypatch.setattr(privilege.os, "geteuid", lambda: 0)
    # Should not raise
    privilege.require_root(action="do a thing")


def test_require_root_raises_when_not_root(monkeypatch):
    monkeypatch.setattr(privilege.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(privilege, "_zehut_binary", lambda: "/home/x/.local/bin/zehut")
    with pytest.raises(privilege.PrivilegeError) as exc:
        privilege.require_root(
            action="create a system user", argv=["user", "create", "alice", "--system"]
        )
    assert "sudo" in exc.value.remediation
    assert "/home/x/.local/bin/zehut" in exc.value.remediation
    assert "user create alice --system" in exc.value.remediation


def test_sudo_command_uses_full_path(monkeypatch):
    monkeypatch.setattr(privilege, "_zehut_binary", lambda: "/opt/zehut/bin/zehut")
    cmd = privilege.sudo_command(["user", "create", "alice"])
    assert cmd == "sudo /opt/zehut/bin/zehut user create alice"


def test_sudo_command_falls_back_to_zehut_when_not_found(monkeypatch):
    monkeypatch.setattr(privilege, "_zehut_binary", lambda: None)
    cmd = privilege.sudo_command(["doctor"])
    assert cmd == "sudo zehut doctor"
