"""Backend strategies — ``system`` and ``logical``."""

from __future__ import annotations

from zehut.backend.base import Backend, ProvisionResult
from zehut.backend.logical import LogicalBackend
from zehut.backend.system import SystemBackend

__all__ = ["Backend", "ProvisionResult", "LogicalBackend", "SystemBackend"]
