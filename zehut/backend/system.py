"""System backend — wraps ``useradd`` and ``userdel``.

The only place in zehut that invokes these binaries. ``PATH`` is pinned to
``/usr/sbin:/usr/bin`` on every call so malicious shadowing in a
privileged caller's environment cannot redirect us to a different binary.
Names are validated against a conservative POSIX-shaped pattern before
any subprocess is spawned.
"""

from __future__ import annotations

import pwd
import re
import subprocess

from zehut.backend.base import Backend, ProvisionResult
from zehut.cli._errors import EXIT_BACKEND, EXIT_USER_ERROR, ZehutError

_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
_SAFE_PATH = "/usr/sbin:/usr/bin"


def _validate_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message=(f"invalid user name {name!r}: must match ^[a-z_][a-z0-9_-]{{0,31}}$"),
            remediation="pick a POSIX-compliant user name (lowercase, digits, dash, underscore)",
        )


def _run(cmd: list[str], *, what: str) -> None:
    result = subprocess.run(
        cmd,
        check=False,
        env={"PATH": _SAFE_PATH, "LC_ALL": "C"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        raise ZehutError(
            code=EXIT_BACKEND,
            message=f"{what} failed (exit {result.returncode}): {stderr or '<no output>'}",
            remediation=f"inspect system logs and re-run {cmd[0]} manually to reproduce",
        )


class SystemBackend(Backend):
    def provision(self, *, name: str) -> ProvisionResult:
        _validate_name(name)
        _run(["useradd", "-m", "-U", "-s", "/bin/bash", name], what="useradd")
        try:
            entry = pwd.getpwnam(name)
        except KeyError as err:  # pragma: no cover — very unlikely after successful useradd
            raise ZehutError(
                code=EXIT_BACKEND,
                message=f"useradd succeeded but {name!r} not found in pwd database",
                remediation="run 'getent passwd' and 'zehut doctor' to diagnose",
            ) from err
        return ProvisionResult(system_user=entry.pw_name, system_uid=entry.pw_uid)

    def deprovision(self, *, name: str, system_user: str | None, keep_home: bool) -> None:
        target = system_user or name
        _validate_name(target)
        cmd = ["userdel"]
        if not keep_home:
            cmd.append("-r")
        cmd.append(target)
        _run(cmd, what="userdel")

    def exists(self, name: str) -> bool:
        try:
            pwd.getpwnam(name)
        except KeyError:
            return False
        return True
