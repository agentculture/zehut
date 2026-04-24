"""stdout/stderr split + JSON switch for all CLI output.

Contract:

* **results** → stdout (``emit_result``). Anything a downstream tool or
  pipe would want to consume.
* **diagnostics** → stderr (``emit_diagnostic``). Progress, warnings, side
  info. Always safe to suppress.
* **errors** → stderr (``emit_error``). Human form is
  ``error: <msg>\\nhint: <remediation>``; JSON form is
  ``{"error": msg, "code": N, "hint": remediation}``.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from zehut.cli._errors import ZehutError


def emit_result(value: Any, *, json_mode: bool) -> None:
    if json_mode:
        sys.stdout.write(json.dumps(value, separators=(",", ":"), default=str))
        sys.stdout.write("\n")
    else:
        if isinstance(value, str):
            sys.stdout.write(value)
            if not value.endswith("\n"):
                sys.stdout.write("\n")
        else:
            sys.stdout.write(f"{value}\n")


def emit_diagnostic(message: str, *, json_mode: bool) -> None:
    if json_mode:
        sys.stderr.write(json.dumps({"diagnostic": message}, separators=(",", ":")))
        sys.stderr.write("\n")
    else:
        sys.stderr.write(f"{message}\n")


def emit_error(err: ZehutError, *, json_mode: bool) -> None:
    if json_mode:
        payload = {"error": err.message, "code": err.code, "hint": err.remediation}
        sys.stderr.write(json.dumps(payload, separators=(",", ":")))
        sys.stderr.write("\n")
    else:
        sys.stderr.write(f"error: {err.message}\n")
        if err.remediation:
            sys.stderr.write(f"hint: {err.remediation}\n")
