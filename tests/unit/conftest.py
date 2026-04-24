"""Shared pytest fixtures for the unit suite.

Consolidates the tmpdir-rooted zehut bootstrap + system backend stubs
that were previously copy-pasted across several test modules (Sonar
flagged the duplication).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def tmp_zehut_root(tmp_path, monkeypatch):
    """Point `/etc/zehut` and `/var/lib/zehut` at throwaway tmpdirs and
    make ``privilege.is_root()`` return True. Returns ``(config_dir,
    state_dir)``.

    Does NOT run ``zehut init`` — callers pick the default backend.
    """
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 0)
    return config_dir, state_dir


@pytest.fixture
def stub_system_backend(monkeypatch):
    """Replace ``SystemBackend.provision``/``deprovision``/``exists``
    with harmless stubs so tests can create system-backed users without
    shelling out to ``useradd``. Returns the injected UID (2000) for
    assertions."""
    from zehut.backend import system as system_mod
    from zehut.backend.base import ProvisionResult

    uid = 2000
    monkeypatch.setattr(
        system_mod.SystemBackend,
        "provision",
        lambda self, *, name: ProvisionResult(system_user=name, system_uid=uid),
    )
    monkeypatch.setattr(
        system_mod.SystemBackend,
        "deprovision",
        lambda self, *, name, system_user, keep_home: None,
    )
    monkeypatch.setattr(system_mod.SystemBackend, "exists", lambda self, name: False)
    return uid
