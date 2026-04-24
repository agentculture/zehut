"""``zehut overview`` — full state snapshot (config + users)."""

from __future__ import annotations

import argparse
from dataclasses import asdict

from zehut import config as cfg_mod
from zehut import users
from zehut.cli._errors import EXIT_STATE, ZehutError
from zehut.cli._output import emit_result


def register(subparsers: "argparse._SubParsersAction") -> None:
    p = subparsers.add_parser("overview", help="Machine-readable snapshot of config + users.")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    try:
        cfg = cfg_mod.load()
    except cfg_mod.ConfigStateError as err:
        raise ZehutError(
            code=EXIT_STATE,
            message=str(err),
            remediation="run: sudo zehut init --domain <d> --default-backend <backend>",
        ) from err
    recs = users.list_all()
    payload = {
        "config": asdict(cfg),
        "users": [users.record_to_dict(r) for r in recs],
    }
    if json_mode:
        emit_result(payload, json_mode=True)
        return 0
    lines = [
        "CONFIG",
        f"  domain:          {cfg.domain}",
        f"  default_backend: {cfg.default_backend}",
        f"  email_pattern:   {cfg.email_pattern}",
        "",
        f"USERS ({len(recs)})",
    ]
    for rec in recs:
        lines.append(
            f"  - {rec.name} [{rec.backend}] email={rec.email} nick={rec.nick} about={rec.about}"
        )
    emit_result("\n".join(lines), json_mode=False)
    return 0
