"""Integration tests for SystemBackend — requires real useradd/userdel.

Gated: only runs as root OR when ``ZEHUT_DOCKER=1`` is set. CI runs these
inside a disposable container. Local dev machines skip them by default.
"""

from __future__ import annotations

import os
import pwd
import uuid

import pytest

from zehut.backend.system import SystemBackend

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.geteuid() != 0 and os.environ.get("ZEHUT_DOCKER") != "1",
        reason="requires root or ZEHUT_DOCKER=1",
    ),
]


def _unique_name() -> str:
    # useradd caps names at 32; take an 8-char hex chunk.
    return "zht" + uuid.uuid4().hex[:8]


def test_provision_then_deprovision_roundtrip():
    name = _unique_name()
    be = SystemBackend()
    try:
        result = be.provision(name=name)
        assert result.system_user == name
        assert isinstance(result.system_uid, int)
        assert be.exists(name) is True
        assert pwd.getpwnam(name).pw_uid == result.system_uid
    finally:
        if be.exists(name):
            be.deprovision(name=name, system_user=name, keep_home=False)
    assert be.exists(name) is False
