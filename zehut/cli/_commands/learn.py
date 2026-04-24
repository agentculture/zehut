"""``zehut learn`` — emit a single agent-consumable skill markdown doc.

The output is copy-pasteable into an agent's skills directory (or piped
into one by an SDK). Keep it terse: the agent reads it once, then reads
``zehut --help`` / ``zehut explain <topic>`` for detail.
"""

from __future__ import annotations

import argparse

from zehut.cli._output import emit_result

_SKILL_BODY = """\
---
name: zehut
description: >
  Drive the zehut CLI to manage local machine identities
  (system-backed and logical) and their emails.
---

# Using zehut

zehut is the identity layer. Every command is ``zehut <noun> <verb>`` or a
top-level global.

## Core commands

- ``zehut init --domain <d> --default-backend system|logical`` — one-time bootstrap. Needs sudo.
- ``zehut user create <name> [--system|--logical] [--nick ..] [--about ..]`` — create a user.
- ``zehut user list [--json]``, ``zehut user show [<name>]`` — read.
- ``zehut user set [<name>] nick=.. about=..`` — mutate metadata (sudo).
- ``zehut user switch <name>`` — logical: prints ``export ZEHUT_IDENTITY=…``
  (use with ``eval``). System: execs ``sudo -u <user> -i``.
- ``zehut user whoami`` (aliased ``current``) — ambient identity.
- ``zehut user delete <name> [--keep-home]`` — remove.
- ``zehut configuration show|set|set-domain`` — config ops (sudo for writes).
- ``zehut doctor`` — read-only health checks.
- ``zehut overview`` — machine-readable snapshot.
- ``zehut explain <topic>`` — prose explanation.

## Conventions

- Every command accepts ``--json`` at the top level: ``zehut --json ...``.
- Errors: stderr ``error: <msg>`` + ``hint: <remediation>``, or a JSON
  object ``{"error", "code", "hint"}`` in ``--json`` mode.
- Ambient identity: if your process runs under a zehut-created OS user,
  ``user show`` / ``user set`` default to that user with no arg.
"""


def register(subparsers: "argparse._SubParsersAction") -> None:
    p = subparsers.add_parser("learn", help="Emit an agent-consumable skill document.")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    emit_result(_SKILL_BODY, json_mode=False)
    return 0
