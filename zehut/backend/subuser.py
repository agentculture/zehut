"""Sub-user (metadata-only) backend.

A sub-user has no OS account; it exists purely in the zehut registry as
a dependent of a system-backed parent. ``provision`` and ``deprovision``
are no-ops at the OS layer; ``exists`` always returns ``False`` because
we define "exists" as "has an OS presence", which sub-users never do.

The parent relationship itself is enforced in :mod:`zehut.users`, not
here — the backend stays narrowly about OS-layer side effects so it can
stay trivially stateless.
"""

from __future__ import annotations

from zehut.backend.base import Backend, ProvisionResult


class SubUserBackend(Backend):
    def provision(self, *, name: str) -> ProvisionResult:
        return ProvisionResult(system_user=None, system_uid=None)

    def deprovision(self, *, name: str, system_user: str | None, keep_home: bool) -> None:
        return None

    def exists(self, name: str) -> bool:
        return False
