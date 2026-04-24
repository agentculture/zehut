"""``zehut user`` noun group — create, list, show, set, delete, switch, whoami.

switch/whoami are added in Task 14; this file after Task 13 carries the
five CRUD verbs plus ``create``.
"""

from __future__ import annotations

import argparse

from zehut import config as cfg_mod
from zehut import privilege, users
from zehut.backend import SubUserBackend, SystemBackend
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
    bg.add_argument("--subuser", dest="backend_choice", action="store_const", const="subuser")
    s.add_argument(
        "--parent",
        default=None,
        help="Parent user name (required with --subuser; parent must be system-backed).",
    )
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
    if backend_name == "subuser":
        return "subuser", SubUserBackend()
    raise ZehutError(
        code=EXIT_STATE,
        message=f"invalid backend {backend_name!r}",
        remediation="configuration.default_backend must be 'system' or 'subuser'",
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
        parent_name=args.parent,
    )
    emit_result(users.record_to_dict(rec), json_mode=json_mode)
    return 0


# --- list ---------------------------------------------------------------------


def _register_list(sub: "argparse._SubParsersAction") -> None:
    s = sub.add_parser("list", help="List zehut users.")
    s.set_defaults(func=_cmd_list)


def _cmd_list(args: argparse.Namespace) -> None:
    # Returns None — _dispatch converts that to EXIT_SUCCESS.
    json_mode = bool(getattr(args, "json", False))
    recs = users.list_all()
    if json_mode:
        emit_result([users.record_to_dict(r) for r in recs], json_mode=True)
        return
    if not recs:
        emit_result("(no users)", json_mode=False)
        return
    by_id = {r.id: r.name for r in recs}
    lines = [f"{'NAME':<20} {'BACKEND':<10} {'PARENT':<20} EMAIL"]
    for rec in recs:
        parent = by_id.get(rec.parent_id or "", "-")
        lines.append(f"{rec.name:<20} {rec.backend:<10} {parent:<20} {rec.email}")
    emit_result("\n".join(lines), json_mode=False)


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
        backend = SubUserBackend()
    cascaded = users.remove(args.name, backend=backend, keep_home=args.keep_home)
    emit_result(
        {"deleted": args.name, "backend": rec.backend, "cascaded_subusers": cascaded},
        json_mode=json_mode,
    )
    return 0


# --- switch -------------------------------------------------------------------


def _register_switch(sub: "argparse._SubParsersAction") -> None:
    s = sub.add_parser(
        "switch",
        help="Switch identity: execs `sudo -u` for system; prints export for sub-users.",
    )
    s.add_argument("name")
    s.set_defaults(func=_cmd_switch)


def _cmd_switch(args: argparse.Namespace) -> int:
    rec = users.get(args.name)
    if rec.backend == "subuser":
        # Print an export line for ``eval $(zehut user switch <name>)``.
        emit_result(f"export ZEHUT_IDENTITY={rec.name}", json_mode=False)
        return 0
    # System-backed: exec a login shell as the OS user. This replaces the
    # current process on success.
    import os

    target = rec.system_user or rec.name
    # Deterministic trusted path — `shutil.which("sudo")` would honour a
    # hostile PATH (Qodo flagged this as path-spoofed-exec). We check the
    # canonical locations in order and fall back if neither exists.
    for candidate in ("/usr/bin/sudo", "/bin/sudo"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            sudo_path = candidate
            break
    else:
        raise ZehutError(
            code=EXIT_STATE,
            message="sudo not found in /usr/bin or /bin",
            remediation="install sudo (e.g. apt install sudo) and re-run",
        )
    try:
        os.execv(sudo_path, [sudo_path, "-u", target, "-i"])  # noqa: S606 # nosec B606
    except OSError as err:
        # sudo missing / not executable / not installed.
        raise ZehutError(
            code=EXIT_STATE,
            message=f"cannot exec sudo ({sudo_path}): {err}",
            remediation="install sudo (e.g. apt install sudo) and re-run",
        ) from err
    # execv only returns on failure; if we get here without OSError, surface
    # a generic internal error rather than pretending success.
    raise ZehutError(  # pragma: no cover — belt-and-suspenders
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
