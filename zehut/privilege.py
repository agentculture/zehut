"""Privilege detection and sudo-advice construction.

Every handler that mutates system state calls :func:`require_root` with a
short ``action`` string and the raw argv of the offending command. On
failure this module raises :class:`PrivilegeError` carrying a ready-to-copy
remediation (``sudo /abs/path/zehut …``) — we resolve the absolute path
because ``uv tool install`` places the binary in ``~/.local/bin`` which is
not on root's ``secure_path`` under typical sudoers configs.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from dataclasses import dataclass


@dataclass
class PrivilegeError(Exception):
    message: str
    remediation: str

    def __str__(self) -> str:  # pragma: no cover — trivial
        return self.message


def is_root() -> bool:
    # ZEHUT_ASSUME_ROOT is a test-only hook (see docs/testing.md) — it lets the
    # self-verify harness exercise privilege-gated commands without running as
    # real root. Not advertised as a user feature.
    if os.environ.get("ZEHUT_ASSUME_ROOT") == "1":
        return True
    return os.geteuid() == 0


def _zehut_binary() -> str | None:
    """Return the absolute path to the running zehut binary, if known."""
    # sys.argv[0] is reliable when invoked as an entry-point script.
    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and os.path.isabs(argv0) and os.path.exists(argv0):
        return argv0
    # Fall back to shutil.which.
    found = shutil.which("zehut")
    return found if found else None


def sudo_command(argv: list[str]) -> str:
    # shlex.join quotes any element containing whitespace or shell
    # metacharacters so the printed remediation is safe to paste verbatim
    # (e.g. --about "QA agent" survives the round-trip).
    binary = _zehut_binary() or "zehut"
    return shlex.join(["sudo", binary, *argv])


def require_root(*, action: str, argv: list[str] | None = None) -> None:
    if is_root():
        return
    argv = argv or []
    remediation = f"re-run with: {sudo_command(argv)}"
    raise PrivilegeError(
        message=f"root privileges required to {action}",
        remediation=remediation,
    )
