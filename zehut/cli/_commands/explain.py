"""``zehut explain <topic>`` — prose explanation of a command or concept."""

from __future__ import annotations

import argparse

from zehut.cli._errors import EXIT_USER_ERROR, ZehutError
from zehut.cli._output import emit_result

_TOPICS: dict[str, str] = {
    "zehut": (
        "zehut is the agents-first identity layer. It manages machine-local users "
        "(system-backed via useradd, plus metadata-only sub-users owned by a "
        "system-backed parent) and assigns each one a deterministic email from a "
        "configured domain. Secrets are NOT in this package — a separate CLI "
        "consumes the users.json registry for that."
    ),
    "user": (
        "A zehut user is an identity with a stable ULID, a human name, optional "
        "nick/about metadata, an auto-generated email, and a backing: 'system' "
        "(real OS user) or 'subuser' (metadata-only, must have a system-backed "
        "parent; cascade-deleted when the parent is deleted)."
    ),
    "user create": (
        "Creates a new user. With --system, zehut runs useradd to provision a "
        "real OS account (requires sudo). With --subuser --parent <name>, it "
        "records a sub-user owned by the named system-backed parent. Without "
        "either flag, uses configuration.default_backend."
    ),
    "user switch": (
        "Switches identity. For system-backed users, execs `sudo -u <user> -i` "
        "(which replaces your shell). For sub-users, prints "
        "`export ZEHUT_IDENTITY=<name>` — pair with `eval $(zehut user switch <name>)`."
    ),
    "user whoami": (
        "Prints the current ambient identity. Resolved in order: (1) OS user if "
        "it matches a system-backed zehut user; (2) $ZEHUT_IDENTITY env var for "
        "sub-users; (3) nothing (exits non-zero)."
    ),
    "subuser": (
        "A sub-user is a metadata-only identity scoped under a system-backed "
        "parent. Use case: one OS user ('an agent') owns multiple dependent "
        "identities ('bots'), each with its own email and ULID. Sub-users "
        "cannot nest (hierarchy is flat: parent must be a top-level system "
        "user). Deleting the parent cascade-deletes every sub-user under it."
    ),
    "configuration": (
        "Machine-wide config lives in /etc/zehut/config.toml. Keys: domain (email "
        "domain), default_backend (system|subuser), email_pattern (tokens: "
        "{name}, {nick}, {id-short}, fallback syntax {nick|name}), "
        "email_collision (suffix)."
    ),
    "doctor": (
        "Read-only health report. Checks: config exists, registry exists, "
        "file modes, useradd on PATH, system users resolve, sub-user names "
        "free, sub-user parents valid, ambient resolution, domain format. "
        "Always exits 0 — inspect --json output."
    ),
    "init": (
        "Bootstraps /etc/zehut/config.toml and /var/lib/zehut/users.json. "
        "Idempotent: safe to re-run. Use --force to overwrite config (never wipes "
        "a non-empty user registry)."
    ),
}


def register(subparsers: "argparse._SubParsersAction") -> None:
    p = subparsers.add_parser("explain", help="Explain a zehut command or concept.")
    p.add_argument("topic", nargs="+", help="e.g. 'user create', 'doctor', 'zehut'")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    key = " ".join(args.topic).strip()
    if key not in _TOPICS:
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message=f"no explanation for {key!r}",
            remediation=f"known topics: {', '.join(sorted(_TOPICS))}",
        )
    emit_result(_TOPICS[key], json_mode=False)
    return 0
