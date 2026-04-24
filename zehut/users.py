"""User registry — CRUD over ``/var/lib/zehut/users.json``.

Every mutation takes the advisory exclusive lock at ``fs.lock_file()``
and writes atomically via ``fs.atomic_write_text``. Backend calls happen
while the lock is held so registry state and OS state cannot diverge due
to a concurrent race inside zehut.

Transactional ordering (spec §5.5):

* ``add`` with system backend: ``backend.provision`` → registry write.
  If the write crashes, a later ``zehut doctor`` detects the orphan OS
  user. (No registry entry ever points at a missing uid.)
* ``remove`` with system backend: registry write → ``backend.deprovision``.
  If deprovision crashes, the registry is clean; ``doctor`` detects the
  orphan OS user.
"""

from __future__ import annotations

import os
import re
import secrets
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from zehut import config, fs
from zehut.backend.base import Backend, ProvisionResult
from zehut.cli._errors import (
    EXIT_CONFLICT,
    EXIT_STATE,
    EXIT_USER_ERROR,
    ZehutError,
)

_SCHEMA_VERSION = 1
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
_EMAIL_DOMAIN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_MUTABLE_KEYS = frozenset({"nick", "about"})
_MAX_EMAIL_SUFFIX = 99


@dataclass(frozen=True)
class UserRecord:
    id: str
    name: str
    nick: str | None
    about: str | None
    email: str
    backend: str
    system_user: str | None
    system_uid: int | None
    created_at: str
    updated_at: str


# --- ULID ---------------------------------------------------------------------


def _generate_ulid() -> str:
    """Generate a 26-char Crockford-base32 ULID. No external deps."""
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand = secrets.randbits(80)
    combined = (ts_ms << 80) | rand
    out: list[str] = []
    for _ in range(26):
        out.append(_CROCKFORD[combined & 0x1F])
        combined >>= 5
    return "".join(reversed(out))


# --- email rendering ----------------------------------------------------------

_TOKEN_RE = re.compile(r"\{([^}]+)\}")


def render_email(
    pattern: str,
    *,
    name: str,
    nick: str | None,
    domain: str,
    id_short: str = "",
) -> str:
    """Render an email local-part from ``pattern`` and join with ``domain``.

    Supports single tokens ``{name}``, ``{nick}``, ``{id-short}`` and the
    fallback syntax ``{a|b|c}`` — first non-empty source wins.
    """
    sources: dict[str, str] = {
        "name": name or "",
        "nick": nick or "",
        "id-short": id_short or "",
    }

    def _replace(match: "re.Match[str]") -> str:
        spec = match.group(1)
        for key in spec.split("|"):
            key = key.strip()
            if key in sources and sources[key]:
                return sources[key]
        return ""

    local = _TOKEN_RE.sub(_replace, pattern).strip()
    if not local:
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message=(
                f"email pattern {pattern!r} produced an empty local-part "
                f"(name={name!r}, nick={nick!r})"
            ),
            remediation="set --nick or change configuration.email_pattern",
        )
    if not _EMAIL_DOMAIN_RE.match(domain):
        raise ZehutError(
            code=EXIT_STATE,
            message=f"invalid configured domain {domain!r}",
            remediation="fix with: sudo zehut configuration set-domain <domain>",
        )
    return f"{local}@{domain}"


# --- registry load/save -------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_registry() -> dict[str, Any]:
    return {"schema_version": _SCHEMA_VERSION, "users": []}


def init_registry() -> None:
    """Create an empty registry file if it doesn't already exist."""
    path = fs.users_file()
    if path.exists():
        return
    import json

    fs.atomic_write_text(path, json.dumps(_empty_registry(), indent=2), mode=0o644)


def _load_raw() -> dict[str, Any]:
    path = fs.users_file()
    try:
        doc = fs.read_json(path)
    except FileNotFoundError as err:
        raise ZehutError(
            code=EXIT_STATE,
            message=f"users registry missing at {path}",
            remediation="run: sudo zehut init",
        ) from err
    if doc.get("schema_version") != _SCHEMA_VERSION:
        raise ZehutError(
            code=EXIT_STATE,
            message=(
                f"unsupported users.json schema_version {doc.get('schema_version')!r}; "
                f"expected {_SCHEMA_VERSION}"
            ),
            remediation="zehut migrate is not yet available (v1); re-init is destructive",
        )
    return doc


def _save_raw(doc: dict[str, Any]) -> None:
    import json

    fs.atomic_write_text(fs.users_file(), json.dumps(doc, indent=2), mode=0o644)


def _to_record(entry: dict[str, Any]) -> UserRecord:
    return UserRecord(
        id=entry["id"],
        name=entry["name"],
        nick=entry.get("nick"),
        about=entry.get("about"),
        email=entry["email"],
        backend=entry["backend"],
        system_user=entry.get("system_user"),
        system_uid=entry.get("system_uid"),
        created_at=entry["created_at"],
        updated_at=entry["updated_at"],
    )


# --- public API ---------------------------------------------------------------


def list_all() -> list[UserRecord]:
    doc = _load_raw()
    return [_to_record(e) for e in doc["users"]]


def get(name: str) -> UserRecord:
    for rec in list_all():
        if rec.name == name:
            return rec
    raise ZehutError(
        code=EXIT_USER_ERROR,
        message=f"no such zehut user {name!r}",
        remediation="list users with: zehut user list",
    )


def _allocate_email(base_email: str, existing_emails: set[str]) -> str:
    if base_email not in existing_emails:
        return base_email
    local, at, domain = base_email.partition("@")
    for n in range(2, _MAX_EMAIL_SUFFIX + 1):
        candidate = f"{local}-{n}@{domain}"
        if candidate not in existing_emails:
            return candidate
    raise ZehutError(
        code=EXIT_CONFLICT,
        message=f"email {base_email!r} collided beyond suffix limit {_MAX_EMAIL_SUFFIX}",
        remediation="pass a distinct --nick or change configuration.email_pattern",
    )


def add(
    *,
    name: str,
    nick: str | None,
    about: str | None,
    backend_name: str,
    backend: Backend,
) -> UserRecord:
    if not _NAME_RE.match(name):
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message=(f"invalid user name {name!r}: must match ^[a-z_][a-z0-9_-]{{0,31}}$"),
            remediation="pick a POSIX-compliant user name",
        )
    cfg = config.load()
    with fs.exclusive_lock(fs.lock_file()):
        doc = _load_raw()
        existing_names = {e["name"] for e in doc["users"]}
        if name in existing_names:
            raise ZehutError(
                code=EXIT_CONFLICT,
                message=f"zehut user {name!r} already exists",
                remediation="pick a different name or edit with: zehut user set",
            )
        new_id = _generate_ulid()
        base_email = render_email(
            cfg.email_pattern,
            name=name,
            nick=nick,
            domain=cfg.domain,
            id_short=new_id[:8],
        )
        existing_emails = {e["email"] for e in doc["users"]}
        email = _allocate_email(base_email, existing_emails)

        provision: ProvisionResult = backend.provision(name=name)
        now = _now_iso()
        entry = {
            "id": new_id,
            "name": name,
            "nick": nick,
            "about": about,
            "email": email,
            "backend": backend_name,
            "system_user": provision.system_user,
            "system_uid": provision.system_uid,
            "created_at": now,
            "updated_at": now,
        }
        doc["users"].append(entry)
        _save_raw(doc)
    return _to_record(entry)


def update(name: str, **fields: Any) -> UserRecord:
    unknown = set(fields) - _MUTABLE_KEYS
    if unknown:
        raise ZehutError(
            code=EXIT_USER_ERROR,
            message=(f"cannot modify {sorted(unknown)}; mutable keys: {sorted(_MUTABLE_KEYS)}"),
            remediation="backend, email, and system_user are immutable in v1",
        )
    with fs.exclusive_lock(fs.lock_file()):
        doc = _load_raw()
        for entry in doc["users"]:
            if entry["name"] == name:
                entry.update({k: v for k, v in fields.items() if k in _MUTABLE_KEYS})
                entry["updated_at"] = _now_iso()
                _save_raw(doc)
                return _to_record(entry)
    raise ZehutError(
        code=EXIT_USER_ERROR,
        message=f"no such zehut user {name!r}",
        remediation="list users with: zehut user list",
    )


def remove(name: str, *, backend: Backend, keep_home: bool) -> None:
    with fs.exclusive_lock(fs.lock_file()):
        doc = _load_raw()
        target = None
        for entry in doc["users"]:
            if entry["name"] == name:
                target = entry
                break
        if target is None:
            raise ZehutError(
                code=EXIT_USER_ERROR,
                message=f"no such zehut user {name!r}",
                remediation="list users with: zehut user list",
            )
        doc["users"] = [e for e in doc["users"] if e["name"] != name]
        _save_raw(doc)
        try:
            backend.deprovision(
                name=name,
                system_user=target.get("system_user"),
                keep_home=keep_home,
            )
        except ZehutError:
            # Registry is already clean; doctor will surface the orphan.
            raise


def ambient_name() -> str | None:
    """Resolve the ambient identity name, or None.

    Order (matches spec §3.4):

    1. OS user matching a zehut-managed system-backed entry.
    2. ``$ZEHUT_IDENTITY`` env var if it names an existing record.
    3. ``None``.
    """
    try:
        import pwd

        os_name = pwd.getpwuid(os.geteuid()).pw_name
    except KeyError:
        os_name = None
    if os_name:
        for rec in list_all():
            if rec.backend == "system" and rec.system_user == os_name:
                return rec.name
    env_name = os.environ.get("ZEHUT_IDENTITY")
    if env_name:
        for rec in list_all():
            if rec.name == env_name:
                return rec.name
    return None


def record_to_dict(rec: UserRecord) -> dict[str, Any]:
    return asdict(rec)
