"""``zehut user`` noun group — create, list, show, set, delete, switch, whoami.

switch/whoami are added in Task 14; this file after Task 13 carries the
five CRUD verbs plus ``create``.
"""

from __future__ import annotations

import argparse

from zehut import config as cfg_mod
from zehut import privilege, users
from zehut.backend import LogicalBackend, SystemBackend
from zehut.backend.base import Backend
from zehut.cli._errors import (
    EXIT_PRIVILEGE,
    EXIT_STATE,
    EXIT_USER_ERROR,
    ZehutError,
)
from zehut.cli._output import emit_result


def register(subparsers: "argparse._SubParsersAction") -> None:
    p = subparsers.add_parser("user", help="Manage zehut users.")
    sub = p.add_subparsers(dest="verb", required=True)

    _register_create(sub)
    _register_list(sub)
    _register_show(sub)
    _register_set(sub)
    _register_delete(sub)
    _register_switch(sub)
    _register_whoami(sub)


# --- create -------------------------------------------------------------------


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


# --- list ---------------------------------------------------------------------


def _register_list(sub: "argparse._SubParsersAction") -> None:
    s = sub.add_parser("list", help="List zehut users.")
    s.set_defaults(func=_cmd_list)


def _cmd_list(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    recs = users.list_all()
    if json_mode:
        emit_result([users.record_to_dict(r) for r in recs], json_mode=True)
        return 0
    if not recs:
        emit_result("(no users)", json_mode=False)
        return 0
    lines = [f"{'NAME':<20} {'BACKEND':<10} EMAIL"]
    for rec in recs:
        lines.append(f"{rec.name:<20} {rec.backend:<10} {rec.email}")
    emit_result("\n".join(lines), json_mode=False)
    return 0


# --- show ---------------------------------------------------------------------


def _register_show(sub: "argparse._SubParsersAction") -> None:
    s = sub.add_parser("show", help="Show a user's record.")
    s.add_argument("name", nargs="?", default=None)
    s.set_defaults(func=_cmd_show)


def _cmd_show(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    name = args.name or users.ambient_name()
    if name is None:
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message="no user name given and no ambient identity",
            remediation="pass <name> or switch with 'zehut user switch <name>'",
        )
    rec = users.get(name)
    if json_mode:
        emit_result(users.record_to_dict(rec), json_mode=True)
    else:
        d = users.record_to_dict(rec)
        lines = [f"{k}: {v}" for k, v in d.items()]
        emit_result("\n".join(lines), json_mode=False)
    return 0


# --- set ----------------------------------------------------------------------


def _register_set(sub: "argparse._SubParsersAction") -> None:
    s = sub.add_parser("set", help="Mutate user metadata (nick, about).")
    s.add_argument("name", nargs="?", default=None)
    s.add_argument("assignments", nargs="+", help="key=value (repeatable)")
    s.set_defaults(func=_cmd_set)


def _parse_assignment(token: str) -> tuple[str, str]:
    if "=" not in token:
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message=f"expected key=value, got {token!r}",
            remediation="use the form 'nick=Ali'",
        )
    key, _, value = token.partition("=")
    if not key:
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message=f"empty key in assignment {token!r}",
            remediation="use the form 'nick=Ali'",
        )
    return key, value


def _cmd_set(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    # If the first assignment arg looks like a name (no '='), ``name`` was
    # consumed by argparse's nargs='?'. Otherwise all tokens are assignments
    # and name comes from ambient.
    name = args.name if args.name and "=" not in args.name else None
    tokens: list[str] = list(args.assignments)
    if args.name and "=" in args.name:
        # argparse put a 'key=value' in 'name'; shift it back.
        tokens.insert(0, args.name)
        name = None
    if name is None:
        name = users.ambient_name()
    if name is None:
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message="no user name given and no ambient identity",
            remediation="pass <name> as the first argument",
        )
    try:
        privilege.require_root(action="modify users.json", argv=["user", "set", name, *tokens])
    except privilege.PrivilegeError as err:
        raise ZehutError(
            code=EXIT_PRIVILEGE, message=err.message, remediation=err.remediation
        ) from err

    fields: dict[str, str] = {}
    for tok in tokens:
        k, v = _parse_assignment(tok)
        fields[k] = v
    rec = users.update(name, **fields)
    emit_result(users.record_to_dict(rec), json_mode=json_mode)
    return 0


# --- delete -------------------------------------------------------------------


def _register_delete(sub: "argparse._SubParsersAction") -> None:
    s = sub.add_parser("delete", help="Remove a zehut user.")
    s.add_argument("name")
    s.add_argument(
        "--keep-home",
        action="store_true",
        help="Don't pass -r to userdel (system-backed only).",
    )
    s.set_defaults(func=_cmd_delete)


def _cmd_delete(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    rec = users.get(args.name)
    if rec.backend == "system":
        try:
            privilege.require_root(
                action="delete a system-backed user",
                argv=["user", "delete", args.name] + (["--keep-home"] if args.keep_home else []),
            )
        except privilege.PrivilegeError as err:
            raise ZehutError(
                code=EXIT_PRIVILEGE, message=err.message, remediation=err.remediation
            ) from err
        backend = SystemBackend()
    else:
        backend = LogicalBackend()
    users.remove(args.name, backend=backend, keep_home=args.keep_home)
    emit_result({"deleted": args.name, "backend": rec.backend}, json_mode=json_mode)
    return 0


# --- switch -------------------------------------------------------------------


def _register_switch(sub: "argparse._SubParsersAction") -> None:
    s = sub.add_parser(
        "switch",
        help="Switch identity: execs `sudo -u` for system; prints export for logical.",
    )
    s.add_argument("name")
    s.set_defaults(func=_cmd_switch)


def _cmd_switch(args: argparse.Namespace) -> int:
    rec = users.get(args.name)
    if rec.backend == "logical":
        # Print an export line for ``eval $(zehut user switch <name>)``.
        emit_result(f"export ZEHUT_IDENTITY={rec.name}", json_mode=False)
        return 0
    # System-backed: exec a login shell as the OS user. This replaces the
    # current process on success.
    import os
    import shutil

    target = rec.system_user or rec.name
    sudo_path = shutil.which("sudo") or "/usr/bin/sudo"
    # sudo itself is trusted; we resolve the absolute path up front so a
    # hostile PATH cannot redirect the exec to a shadow binary.
    os.execv(sudo_path, [sudo_path, "-u", target, "-i"])  # noqa: S606
    # If execv returns, something broke.
    raise ZehutError(  # pragma: no cover — execv only returns on failure
        code=EXIT_STATE,
        message="execv returned unexpectedly",
        remediation="verify sudo is installed and on PATH",
    )


# --- whoami / current ---------------------------------------------------------


def _register_whoami(sub: "argparse._SubParsersAction") -> None:
    for verb in ("whoami", "current"):
        s = sub.add_parser(verb, help="Print the ambient zehut identity.")
        s.set_defaults(func=_cmd_whoami)


def _cmd_whoami(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    name = users.ambient_name()
    if name is None:
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message="no current zehut user",
            remediation="run 'zehut user switch <name>' or 'zehut user create <name>'",
        )
    rec = users.get(name)
    if json_mode:
        emit_result(users.record_to_dict(rec), json_mode=True)
    else:
        emit_result(f"{rec.name} ({rec.backend}, email={rec.email})", json_mode=False)
    return 0
