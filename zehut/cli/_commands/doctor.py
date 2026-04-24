"""``zehut doctor`` — read-only system health report.

Eight checks from spec §6.3. Each check returns a dict with ``name``,
``status`` (``PASS`` | ``FAIL`` | ``WARN``), ``detail``, and
``remediation``. The command itself always exits 0: it's a report, not a
gate. Callers who want a non-zero exit on any FAIL should inspect the
JSON output (``--json``) and react accordingly.
"""

from __future__ import annotations

import argparse
import os
import pwd
import re
import shutil
from dataclasses import dataclass

from zehut import config as cfg_mod
from zehut import fs, users
from zehut.cli._output import emit_result

_DOMAIN_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass
class Check:
    name: str
    status: str
    detail: str
    remediation: str


def register(subparsers: "argparse._SubParsersAction") -> None:
    p = subparsers.add_parser("doctor", help="Read-only health check.")
    p.set_defaults(func=run)


def _check_config_exists() -> Check:
    path = fs.config_file()
    if path.exists():
        return Check("config_exists", "PASS", str(path), "")
    return Check(
        "config_exists",
        "FAIL",
        f"{path} missing",
        "run: sudo zehut init --domain <d> --default-backend <backend>",
    )


def _check_users_exists() -> Check:
    path = fs.users_file()
    if path.exists():
        return Check("users_exists", "PASS", str(path), "")
    return Check(
        "users_exists",
        "FAIL",
        f"{path} missing",
        "run: sudo zehut init ... (or 'zehut init --force' to rebuild)",
    )


def _check_file_modes() -> Check:
    cfg_path = fs.config_file()
    users_path = fs.users_file()
    problems: list[str] = []
    for p in (cfg_path, users_path):
        if not p.exists():
            continue
        mode = p.stat().st_mode & 0o777
        if mode != 0o644:
            problems.append(f"{p} mode={oct(mode)} (expected 0o644)")
    if problems:
        return Check(
            "file_modes",
            "WARN",
            "; ".join(problems),
            "fix with: sudo chmod 644 <path>",
        )
    return Check("file_modes", "PASS", "0o644", "")


def _check_useradd_on_path() -> Check:
    # Only relevant if any system-backed users exist.
    try:
        has_system = any(r.backend == "system" for r in users.list_all())
    except Exception:
        has_system = False
    if not has_system:
        return Check("useradd_available", "PASS", "not required", "")
    for binary in ("useradd", "userdel", "id"):
        if shutil.which(binary) is None:
            return Check(
                "useradd_available",
                "FAIL",
                f"{binary} not on PATH",
                "install the 'shadow' / 'shadow-utils' package for your distro",
            )
    return Check("useradd_available", "PASS", "useradd, userdel, id on PATH", "")


def _check_system_users_resolve() -> Check:
    try:
        recs = users.list_all()
    except Exception as err:
        return Check("system_users_resolve", "FAIL", str(err), "inspect /var/lib/zehut/users.json")
    problems: list[str] = []
    for rec in recs:
        if rec.backend != "system":
            continue
        target = rec.system_user or rec.name
        try:
            entry = pwd.getpwnam(target)
        except KeyError:
            problems.append(f"{rec.name}: OS user {target!r} missing")
            continue
        if entry.pw_uid != rec.system_uid:
            problems.append(f"{rec.name}: uid drift (registry={rec.system_uid}, os={entry.pw_uid})")
    if problems:
        return Check(
            "system_users_resolve",
            "FAIL",
            "; ".join(problems),
            "reconcile manually in v1; 'zehut doctor --adopt' is v2",
        )
    return Check("system_users_resolve", "PASS", f"{len(recs)} users consistent", "")


def _check_logical_name_vs_os() -> Check:
    try:
        recs = users.list_all()
    except Exception:
        return Check("logical_names_free", "PASS", "registry unreadable; skipped", "")
    collisions: list[str] = []
    for rec in recs:
        if rec.backend != "logical":
            continue
        try:
            pwd.getpwnam(rec.name)
            collisions.append(rec.name)
        except KeyError:
            continue
    if collisions:
        return Check(
            "logical_names_free",
            "WARN",
            f"logical names also exist as OS users: {collisions}",
            "rename (v2) or delete the colliding logical user",
        )
    return Check("logical_names_free", "PASS", "no collisions", "")


def _check_ambient_resolution() -> Check:
    try:
        os_name = pwd.getpwuid(os.geteuid()).pw_name
    except KeyError:
        return Check("ambient_resolution", "PASS", "no OS user for euid", "")
    try:
        recs = users.list_all()
    except Exception:
        return Check("ambient_resolution", "PASS", "registry unreadable; skipped", "")
    for rec in recs:
        if rec.backend == "system" and rec.system_user == os_name:
            return Check(
                "ambient_resolution",
                "PASS",
                f"current OS user {os_name!r} resolves to zehut {rec.name!r}",
                "",
            )
    return Check(
        "ambient_resolution",
        "PASS",
        f"current OS user {os_name!r} is not zehut-managed",
        "",
    )


def _check_domain_format() -> Check:
    try:
        cfg = cfg_mod.load()
    except cfg_mod.ConfigStateError as err:
        return Check("domain_format", "FAIL", str(err), "run: sudo zehut init ...")
    if _DOMAIN_RE.match(cfg.domain):
        return Check("domain_format", "PASS", cfg.domain, "")
    return Check(
        "domain_format",
        "FAIL",
        f"{cfg.domain!r} not a valid-looking domain",
        "fix with: sudo zehut configuration set-domain <domain>",
    )


_CHECKS = (
    _check_config_exists,
    _check_users_exists,
    _check_file_modes,
    _check_useradd_on_path,
    _check_system_users_resolve,
    _check_logical_name_vs_os,
    _check_ambient_resolution,
    _check_domain_format,
)


def run(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    results = [c() for c in _CHECKS]
    if json_mode:
        emit_result(
            {
                "checks": [
                    {
                        "name": r.name,
                        "status": r.status,
                        "detail": r.detail,
                        "remediation": r.remediation,
                    }
                    for r in results
                ]
            },
            json_mode=True,
        )
        return 0

    lines = []
    for r in results:
        marker = {"PASS": "+", "WARN": "!", "FAIL": "x"}.get(r.status, "?")  # noqa: S105
        line = f"{marker} [{r.status}] {r.name}: {r.detail}"
        lines.append(line)
        if r.remediation:
            lines.append(f"    hint: {r.remediation}")
    emit_result("\n".join(lines), json_mode=False)
    return 0
