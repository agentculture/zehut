"""Filesystem primitives: path resolution, locking, atomic writes.

Every other module delegates to this one for anything touching disk. The
env overrides ``ZEHUT_CONFIG_DIR`` and ``ZEHUT_STATE_DIR`` exist for tests
and are not a user-facing feature (see docs/testing.md).

Locking: ``exclusive_lock`` and ``shared_lock`` are thin ``fcntl.flock``
context managers over ``/var/lib/zehut/.lock``. Advisory only — nothing
outside zehut participates — but enough to serialise zehut's own writers
against readers on a single host.

Atomic writes: write to a temp sibling, fsync, then ``os.replace``. On
POSIX this is atomic w.r.t. crashes; readers see either the old file or
the new one, never a half-written blob.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_DEFAULT_CONFIG_DIR = Path("/etc/zehut")
_DEFAULT_STATE_DIR = Path("/var/lib/zehut")


def config_dir() -> Path:
    return Path(os.environ.get("ZEHUT_CONFIG_DIR", str(_DEFAULT_CONFIG_DIR)))


def state_dir() -> Path:
    return Path(os.environ.get("ZEHUT_STATE_DIR", str(_DEFAULT_STATE_DIR)))


def config_file() -> Path:
    return config_dir() / "config.toml"


def users_file() -> Path:
    return state_dir() / "users.json"


def lock_file() -> Path:
    return state_dir() / ".lock"


def atomic_write_text(target: Path, data: str, *, mode: int) -> None:
    """Write ``data`` to ``target`` atomically, creating parents if needed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def read_json(target: Path) -> Any:
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@contextmanager
def _locked(path: Path, op: int) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Open O_RDWR so both LOCK_SH and LOCK_EX work on the same fd.
    flags = os.O_RDWR | os.O_CREAT
    fd = os.open(str(path), flags, 0o644)
    try:
        fcntl.flock(fd, op)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        try:
            os.close(fd)
        except OSError as err:
            if err.errno != errno.EBADF:
                raise


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    """Hold ``LOCK_EX`` on ``path`` for the duration of the context."""
    with _locked(path, fcntl.LOCK_EX):
        yield


@contextmanager
def shared_lock(path: Path) -> Iterator[None]:
    """Hold ``LOCK_SH`` on ``path`` for the duration of the context."""
    with _locked(path, fcntl.LOCK_SH):
        yield
