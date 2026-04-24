"""Backend strategies — ``system`` and ``subuser``."""

from __future__ import annotations

from zehut.backend.base import Backend, ProvisionResult
from zehut.backend.subuser import SubUserBackend
from zehut.backend.system import SystemBackend

__all__ = ["Backend", "ProvisionResult", "SubUserBackend", "SystemBackend"]
