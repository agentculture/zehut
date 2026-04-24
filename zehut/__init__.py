"""zehut — agents-first identity layer.

Exposes the package version via importlib.metadata so pyproject.toml is the
single source of truth. No other top-level re-exports; callers import from
submodules directly (`from zehut.users import Registry`, etc.).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("zehut")
except PackageNotFoundError:  # pragma: no cover — only hit in uninstalled dev trees
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
