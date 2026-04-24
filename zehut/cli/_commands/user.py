"""``zehut user`` noun group.

Registers the ``user`` parser and its verbs. Each verb lives as a small
handler function below. More verbs (list/show/set/switch/whoami/delete)
are added in subsequent tasks.
"""

from __future__ import annotations

import argparse

from zehut import config as cfg_mod
from zehut import privilege, users
from zehut.backend import LogicalBackend, SystemBackend
from zehut.backend.base import Backend
from zehut.cli._errors import EXIT_PRIVILEGE, EXIT_STATE, ZehutError
from zehut.cli._output import emit_result


def register(subparsers: "argparse._SubParsersAction") -> None:
    p = subparsers.add_parser("user", help="Manage zehut users.")
    sub = p.add_subparsers(dest="verb", required=True)

    _register_create(sub)


def _register_create(sub: "argparse._SubParsersAction") -> None:
    s = sub.add_parser("create", help="Create a new zehut user.")
    s.add_argument("name")
    bg = s.add_mutually_exclusive_group()
    bg.add_argument("--system", dest="backend_choice", action="store_const", const="system")
    bg.add_argument("--logical", dest="backend_choice", action="store_const", const="logical")
    s.add_argument("--nick", default=None)
    s.add_argument("--about", default=None)
    s.set_defaults(func=_cmd_create)


def _resolve_backend(choice: str | None) -> tuple[str, Backend]:
    try:
        cfg = cfg_mod.load()
    except cfg_mod.ConfigStateError as err:
        raise ZehutError(
            code=EXIT_STATE,
            message=str(err),
            remediation="run: sudo zehut init --domain <d> --default-backend <backend>",
        ) from err
    backend_name = choice or cfg.default_backend
    if backend_name == "system":
        return "system", SystemBackend()
    if backend_name == "logical":
        return "logical", LogicalBackend()
    raise ZehutError(
        code=EXIT_STATE,
        message=f"invalid backend {backend_name!r}",
        remediation="configuration.default_backend must be 'system' or 'logical'",
    )


def _cmd_create(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    backend_name, backend = _resolve_backend(args.backend_choice)
    if backend_name == "system":
        try:
            privilege.require_root(
                action="create a system-backed user",
                argv=["user", "create", args.name, "--system"],
            )
        except privilege.PrivilegeError as err:
            raise ZehutError(
                code=EXIT_PRIVILEGE, message=err.message, remediation=err.remediation
            ) from err

    rec = users.add(
        name=args.name,
        nick=args.nick,
        about=args.about,
        backend_name=backend_name,
        backend=backend,
    )
    emit_result(users.record_to_dict(rec), json_mode=json_mode)
    return 0
