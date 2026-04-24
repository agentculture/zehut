"""Filesystem primitives: path resolution, locking, atomic writes.

Every other module delegates to this one for anything touching disk. The
env overrides ``ZEHUT_CONFIG_DIR`` and ``ZEHUT_STATE_DIR`` exist for tests
and are not a user-facing feature (see docs/testing.md).

Locking: ``exclusive_lock`` and ``shared_lock`` are thin ``fcntl.flock``
context managers over ``/var/lib/zehut/.lock``. Advisory only — nothing
outside zehut participates — but enough to serialise zehut's own writers
against readers on a single host.

Caution: ``exclusive_lock`` and ``shared_lock`` are NOT re-entrant on the same
thread. Each call opens a fresh fd, and the kernel treats separate open file
descriptions as independent lock holders — acquiring the same lock path twice
without releasing between calls will deadlock. Never nest calls on one lock
path; acquire at the operation boundary.

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
    # os.fdopen takes ownership of fd on success. If it raises before that,
    # we must close fd ourselves — otherwise the raw fd leaks.
    fd_owned = False
    try:
        fh = os.fdopen(fd, "w", encoding="utf-8")
        fd_owned = True
        with fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, target)
    except BaseException:
        if not fd_owned:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def read_json(target: Path) -> Any:
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@contextmanager
def _locked(path: Path, op: int, *, create: bool) -> Iterator[None]:
    """Flock context — open mode depends on whether we need write access.

    Exclusive writers pass ``create=True`` so the lock file is auto-created
    (the writer is root and allowed to). Shared readers pass ``create=False``
    and open ``O_RDONLY`` so non-root readers can take a read lock on a
    root-owned, 0o644 lock file — `LOCK_SH` does not require the fd to be
    writable.
    """
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_RDWR | os.O_CREAT
        fd = os.open(str(path), flags, 0o644)
    else:
        # Read path: do NOT mkdir, do NOT create. If the lock file is absent
        # the registry hasn't been initialised — let the caller's load raise
        # a proper ZehutError(EXIT_STATE) from FileNotFoundError instead of
        # us papering over it by creating state directories we can't own.
        flags = os.O_RDONLY
        fd = os.open(str(path), flags)
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
    """Hold ``LOCK_EX`` on ``path`` for the duration of the context.

    Creates the lock file (and its parent) if missing. Intended for root-run
    mutating paths; non-root callers will hit EACCES on `/var/lib/zehut`.
    """
    with _locked(path, fcntl.LOCK_EX, create=True):
        yield


@contextmanager
def shared_lock(path: Path) -> Iterator[None]:
    """Hold ``LOCK_SH`` on ``path`` for the duration of the context.

    Read-only: opens the lock file ``O_RDONLY`` and does not create state
    directories. Safe for non-root readers against a root-owned lock file
    (0o644). Raises ``FileNotFoundError`` if the lock file doesn't exist —
    callers should translate that into a meaningful EXIT_STATE error.
    """
    with _locked(path, fcntl.LOCK_SH, create=False):
        yield
