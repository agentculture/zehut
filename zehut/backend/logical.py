"""Logical (metadata-only) backend.

A logical identity has no OS account; it exists purely in the zehut
registry. ``provision`` and ``deprovision`` are no-ops at the OS layer;
``exists`` always returns ``False`` because we define "exists" as "has an
OS presence", which logical identities never do.
"""

from __future__ import annotations

from zehut.backend.base import Backend, ProvisionResult


class LogicalBackend(Backend):
    def provision(self, *, name: str) -> ProvisionResult:
        return ProvisionResult(system_user=None, system_uid=None)

    def deprovision(self, *, name: str, system_user: str | None, keep_home: bool) -> None:
        return None

    def exists(self, name: str) -> bool:
        return False
