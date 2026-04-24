"""Backend strategies — ``system`` and ``logical``.

Both share the :class:`~zehut.backend.base.Backend` ABC so
``zehut.users`` can treat them uniformly.
"""

from __future__ import annotations

from zehut.backend.base import Backend, ProvisionResult
from zehut.backend.logical import LogicalBackend

__all__ = ["Backend", "ProvisionResult", "LogicalBackend"]
