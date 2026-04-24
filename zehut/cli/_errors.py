"""Structured error type + exit-code constants.

Every CLI handler that fails raises :class:`ZehutError`. ``zehut.cli.main``
catches it, routes through :mod:`zehut.cli._output`, and exits with the
embedded code. Python tracebacks never reach the user; unknown exceptions
are wrapped into ``ZehutError(EXIT_INTERNAL, ...)`` at the top level.
"""

from __future__ import annotations

from dataclasses import dataclass

EXIT_SUCCESS = 0
EXIT_USER_ERROR = 64
EXIT_STATE = 65
EXIT_PRIVILEGE = 66
EXIT_BACKEND = 67
EXIT_CONFLICT = 68
EXIT_INTERNAL = 70


@dataclass
class ZehutError(Exception):
    code: int
    message: str
    remediation: str

    def __str__(self) -> str:
        return self.message
