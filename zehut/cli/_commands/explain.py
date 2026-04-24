"""``zehut explain <topic>`` — prose explanation of a command or concept."""

from __future__ import annotations

import argparse

from zehut.cli._errors import EXIT_USER_ERROR, ZehutError
from zehut.cli._output import emit_result

_TOPICS: dict[str, str] = {
    "zehut": (
        "zehut is the agents-first identity layer. It manages machine-local users "
        "(system-backed via useradd, or logical/metadata-only) and assigns each one "
        "a deterministic email from a configured domain. Secrets are NOT in this "
        "package — a separate CLI consumes the users.json registry for that."
    ),
    "user": (
        "A zehut user is an identity with a stable ULID, a human name, optional "
        "nick/about metadata, an auto-generated email, and a backing: 'system' "
        "(real OS user) or 'logical' (metadata only)."
    ),
    "user create": (
        "Creates a new user. With --system, zehut runs useradd to provision a real "
        "OS account (requires sudo). With --logical, it records metadata only. "
        "Without either flag, uses configuration.default_backend."
    ),
    "user switch": (
        "Switches identity. For system-backed users, execs `sudo -u <user> -i` "
        "(which replaces your shell). For logical users, prints "
        "`export ZEHUT_IDENTITY=<name>` — pair with `eval $(zehut user switch <name>)`."
    ),
    "user whoami": (
        "Prints the current ambient identity. Resolved in order: (1) OS user if "
        "it matches a system-backed zehut user; (2) $ZEHUT_IDENTITY env var for "
        "logical users; (3) nothing (exits non-zero)."
    ),
    "configuration": (
        "Machine-wide config lives in /etc/zehut/config.toml. Keys: domain (email "
        "domain), default_backend (system|logical), email_pattern (tokens: "
        "{name}, {nick}, {id-short}, fallback syntax {nick|name}), "
        "email_collision (suffix)."
    ),
    "doctor": (
        "Read-only health report. Eight checks: config exists, registry exists, "
        "file modes, useradd on PATH, system users resolve, logical names free, "
        "ambient resolution, domain format. Always exits 0 — inspect --json output."
    ),
    "init": (
        "Bootstraps /etc/zehut/config.toml and /var/lib/zehut/users.json. "
        "Idempotent: safe to re-run. Use --force to overwrite config (never wipes "
        "a non-empty user registry)."
    ),
}


def register(subparsers: "argparse._SubParsersAction") -> None:
    p = subparsers.add_parser("explain", help="Explain a zehut command or concept.")
    p.add_argument("topic", help="e.g. 'user create', 'doctor', 'zehut'")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    key = args.topic.strip()
    if key not in _TOPICS:
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message=f"no explanation for {args.topic!r}",
            remediation=f"known topics: {', '.join(sorted(_TOPICS))}",
        )
    emit_result(_TOPICS[key], json_mode=False)
    return 0
