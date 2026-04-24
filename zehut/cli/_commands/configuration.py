"""``zehut configuration`` — show and mutate ``/etc/zehut/config.toml``.

Verbs:

* ``show``          — render current config (text or JSON).
* ``set``           — set a named key; delegates to :func:`zehut.config.set_key`.
* ``set-domain``    — convenience shortcut for the most common mutation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict

from zehut import config, privilege
from zehut.cli._errors import EXIT_PRIVILEGE, EXIT_STATE, ZehutError
from zehut.cli._output import emit_result


def register(subparsers: "argparse._SubParsersAction") -> None:
    p = subparsers.add_parser("configuration", help="Show or modify zehut configuration.")
    sub = p.add_subparsers(dest="verb", required=True)

    s_show = sub.add_parser("show", help="Render the current configuration.")
    s_show.set_defaults(func=_cmd_show)

    s_set = sub.add_parser("set", help="Set a configuration key.")
    s_set.add_argument("key")
    s_set.add_argument("value")
    s_set.set_defaults(func=_cmd_set)

    s_sd = sub.add_parser("set-domain", help="Shortcut for 'configuration set domain <value>'.")
    s_sd.add_argument("domain")
    s_sd.set_defaults(func=_cmd_set_domain)


def _cmd_show(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    try:
        cfg = config.load()
    except config.ConfigStateError as err:
        raise ZehutError(
            code=EXIT_STATE,
            message=str(err),
            remediation="run: sudo zehut init --domain <d> --default-backend <backend>",
        ) from err
    payload = asdict(cfg)
    if json_mode:
        emit_result(payload, json_mode=True)
    else:
        lines = [
            f"schema_version: {payload['schema_version']}",
            f"domain:          {payload['domain']}",
            f"default_backend: {payload['default_backend']}",
            f"email_pattern:   {payload['email_pattern']}",
            f"email_collision: {payload['email_collision']}",
        ]
        emit_result("\n".join(lines), json_mode=False)
    return 0


def _require_root(argv: list[str]) -> None:
    try:
        privilege.require_root(action="modify /etc/zehut/config.toml", argv=argv)
    except privilege.PrivilegeError as err:
        raise ZehutError(
            code=EXIT_PRIVILEGE, message=err.message, remediation=err.remediation
        ) from err


def _cmd_set(args: argparse.Namespace) -> int:
    _require_root(["configuration", "set", args.key, args.value])
    try:
        config.set_key(args.key, args.value)
    except config.ConfigStateError as err:
        raise ZehutError(
            code=EXIT_STATE, message=str(err), remediation="zehut configuration show"
        ) from err
    return _cmd_show(args)


def _cmd_set_domain(args: argparse.Namespace) -> int:
    _require_root(["configuration", "set-domain", args.domain])
    try:
        config.set_key("domain", args.domain)
    except config.ConfigStateError as err:
        raise ZehutError(
            code=EXIT_STATE, message=str(err), remediation="zehut configuration show"
        ) from err
    return _cmd_show(args)
