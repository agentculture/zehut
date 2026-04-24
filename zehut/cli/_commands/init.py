"""``zehut init`` — bootstrap config + users registry.

Idempotent by default: if state already exists, re-running without
``--force`` is a no-op that reports the current configuration. With
``--force``, the existing ``config.toml`` is rewritten and the registry
file is (re)created empty only if no users exist; otherwise ``--force``
still refuses to wipe data.
"""

from __future__ import annotations

import argparse

from zehut import config, fs, privilege, users
from zehut.cli._errors import EXIT_CONFLICT, EXIT_PRIVILEGE, EXIT_STATE, ZehutError
from zehut.cli._output import emit_diagnostic, emit_result


def register(subparsers: "argparse._SubParsersAction") -> None:
    p = subparsers.add_parser("init", help="Bootstrap zehut state on this machine.")
    p.add_argument("--domain", required=True, help="Email domain, e.g. agents.example.com")
    p.add_argument(
        "--default-backend",
        required=True,
        choices=("system", "logical"),
        help="Default backend for 'zehut user create'.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config.toml (never deletes users from a non-empty registry).",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    # Returns None on every success path — _dispatch converts that to
    # EXIT_SUCCESS. Failure paths raise ZehutError with their own code.
    json_mode = bool(getattr(args, "json", False))
    try:
        privilege.require_root(
            action="write /etc/zehut and /var/lib/zehut",
            argv=["init", "--domain", args.domain, "--default-backend", args.default_backend],
        )
    except privilege.PrivilegeError as err:
        raise ZehutError(
            code=EXIT_PRIVILEGE, message=err.message, remediation=err.remediation
        ) from err

    cfg_path = fs.config_file()
    already = cfg_path.exists()
    if already and not args.force:
        emit_diagnostic(f"zehut already initialised at {cfg_path}", json_mode=json_mode)
        try:
            existing = config.load()
        except config.ConfigStateError as err:
            # Corrupt/unreadable config in the idempotent branch should
            # surface as EXIT_STATE with a clear hint, not EXIT_INTERNAL.
            raise ZehutError(
                code=EXIT_STATE,
                message=str(err),
                remediation="fix the TOML or re-run with: sudo zehut init --force ...",
            ) from err
        users.init_registry()  # ensure users.json exists even after partial prior init
        emit_result(
            {
                "initialised": False,
                "domain": existing.domain,
                "default_backend": existing.default_backend,
                "config_path": str(cfg_path),
                "users_path": str(fs.users_file()),
            },
            json_mode=json_mode,
        )
        return

    if already and args.force:
        # Guard: never wipe a non-empty registry implicitly.
        try:
            current = users.list_all()
        except ZehutError:
            current = []
        if current:
            raise ZehutError(
                code=EXIT_CONFLICT,
                message=(
                    f"refusing to --force init with {len(current)} existing users in the registry"
                ),
                remediation="delete users individually with 'zehut user delete' first",
            )

    cfg = config.Config.default(domain=args.domain, backend=args.default_backend)
    config.save(cfg)
    users.init_registry()
    emit_result(
        {
            "initialised": True,
            "domain": cfg.domain,
            "default_backend": cfg.default_backend,
            "config_path": str(cfg_path),
            "users_path": str(fs.users_file()),
        },
        json_mode=json_mode,
    )
