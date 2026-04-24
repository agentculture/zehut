"""Unit tests for zehut.backend.logical."""

from __future__ import annotations

from zehut.backend import logical
from zehut.backend.base import Backend, ProvisionResult


def test_logical_backend_is_a_backend():
    assert isinstance(logical.LogicalBackend(), Backend)


def test_provision_returns_result_with_no_system_uid():
    be = logical.LogicalBackend()
    result = be.provision(name="alice")
    assert isinstance(result, ProvisionResult)
    assert result.system_user is None
    assert result.system_uid is None


def test_deprovision_is_a_noop():
    be = logical.LogicalBackend()
    # Should not raise regardless of whether 'alice' exists anywhere.
    be.deprovision(name="alice", system_user=None, keep_home=False)


def test_exists_returns_false_for_any_name():
    be = logical.LogicalBackend()
    assert be.exists("alice") is False
    assert be.exists("root") is False
