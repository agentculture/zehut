"""Backend ABC and shared types.

A backend encapsulates OS-level identity plumbing: creation, deletion,
existence checks. ``zehut.users`` owns the registry (metadata) and calls
into a backend for the OS side.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ProvisionResult:
    """Outcome of a successful provision."""

    system_user: str | None
    system_uid: int | None


class Backend(ABC):
    """Abstract backend interface."""

    @abstractmethod
    def provision(self, *, name: str) -> ProvisionResult: ...

    @abstractmethod
    def deprovision(self, *, name: str, system_user: str | None, keep_home: bool) -> None: ...

    @abstractmethod
    def exists(self, name: str) -> bool: ...
