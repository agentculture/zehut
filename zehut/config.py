"""Configuration file (``/etc/zehut/config.toml``) — load, save, validate.

The on-disk format is stable as ``schema_version = 1``. Parsing uses
``tomllib`` (stdlib, read-only); writing is hand-rolled because the
serialiser in ``tomllib`` doesn't exist and pulling in ``tomli-w`` would
add a runtime dependency for ~30 lines of work.

This module never touches the users registry; that is ``zehut.users``'s
job. Cross-file consistency checks live in ``zehut.cli._commands.doctor``.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import Literal, cast

from zehut import fs

Backend = Literal["system", "subuser"]
CollisionMode = Literal["suffix"]

_SCHEMA_VERSION = 1
_VALID_BACKENDS: tuple[Backend, ...] = ("system", "subuser")
_VALID_COLLISION: tuple[CollisionMode, ...] = ("suffix",)
_SETTABLE_KEYS = frozenset({"domain", "default_backend", "email_pattern", "email_collision"})


class ConfigStateError(Exception):
    """Raised for any config problem routable to EXIT_STATE (65)."""


@dataclass(frozen=True)
class Config:
    schema_version: int
    domain: str
    default_backend: Backend
    email_pattern: str
    email_collision: CollisionMode

    @classmethod
    def default(cls, *, domain: str, backend: Backend) -> "Config":
        if backend not in _VALID_BACKENDS:
            raise ConfigStateError(f"invalid backend {backend!r}")
        return cls(
            schema_version=_SCHEMA_VERSION,
            domain=domain,
            default_backend=backend,
            email_pattern="{name}",
            email_collision="suffix",
        )


_TOML_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
}


def _toml_str(value: str) -> str:
    """Escape ``value`` for emission as a TOML basic string (double-quoted).

    TOML basic strings must escape backslash, double quote, and control
    characters. Without this, a domain or pattern containing ``"`` or ``\\``
    would produce invalid TOML and break the next ``load()``.
    """
    escaped = value
    for ch, sub in _TOML_ESCAPES.items():
        escaped = escaped.replace(ch, sub)
    # Reject any remaining raw control characters (U+0000..U+001F minus the
    # ones handled above, plus U+007F). They're technically escapable as
    # \uXXXX but we have no use case and rejecting is safer.
    for ch in escaped:
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            raise ConfigStateError(f"value contains unsupported control character U+{ord(ch):04X}")
    return f'"{escaped}"'


def _serialise(cfg: Config) -> str:
    return (
        f"schema_version = {cfg.schema_version}\n"
        "\n"
        "[defaults]\n"
        f"backend = {_toml_str(cfg.default_backend)}\n"
        "\n"
        "[email]\n"
        f"domain = {_toml_str(cfg.domain)}\n"
        f"pattern = {_toml_str(cfg.email_pattern)}\n"
        f"collision = {_toml_str(cfg.email_collision)}\n"
    )


def save(cfg: Config) -> None:
    fs.atomic_write_text(fs.config_file(), _serialise(cfg), mode=0o644)


def load() -> Config:
    path = fs.config_file()
    try:
        raw = path.read_bytes()
    except FileNotFoundError as err:
        raise ConfigStateError(f"zehut is not initialized: {path} is missing") from err
    try:
        doc = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as err:
        raise ConfigStateError(f"invalid TOML in {path}: {err}") from err

    schema = doc.get("schema_version")
    if schema != _SCHEMA_VERSION:
        raise ConfigStateError(
            f"unsupported schema_version {schema!r} in {path}; expected {_SCHEMA_VERSION}"
        )
    defaults = doc.get("defaults", {})
    email = doc.get("email", {})
    backend = defaults.get("backend")
    if backend not in _VALID_BACKENDS:
        raise ConfigStateError(
            f"invalid [defaults].backend {backend!r}; expected one of {list(_VALID_BACKENDS)}"
        )
    domain = email.get("domain")
    if not isinstance(domain, str) or not domain:
        raise ConfigStateError(f"missing or empty [email].domain in {path}")
    pattern = email.get("pattern", "{name}")
    collision = email.get("collision", "suffix")
    if collision not in _VALID_COLLISION:
        raise ConfigStateError(
            f"invalid [email].collision {collision!r}; expected one of {list(_VALID_COLLISION)}"
        )
    return Config(
        schema_version=_SCHEMA_VERSION,
        domain=domain,
        default_backend=backend,
        email_pattern=pattern,
        email_collision=collision,
    )


def set_key(key: str, value: str) -> None:
    """Mutate a single top-level config field and persist.

    ``key`` is one of :data:`_SETTABLE_KEYS`. ``value`` is always accepted
    as a string; type coercion/validation happens inside :func:`load` on
    the next read.
    """
    if key not in _SETTABLE_KEYS:
        raise ConfigStateError(
            f"unknown config key {key!r}; settable keys: {sorted(_SETTABLE_KEYS)}"
        )
    cfg = load()
    # Start from the current Config values, then overwrite the one being
    # set. Building a fresh Config explicitly (instead of chaining
    # ``dataclasses.replace`` across an if/elif) makes the resulting type
    # unambiguous to Sonar's type-flow (python:S5655) without `cast`.
    domain = cfg.domain
    default_backend: Backend = cfg.default_backend
    email_pattern = cfg.email_pattern
    email_collision: CollisionMode = cfg.email_collision
    if key == "domain":
        domain = value
    elif key == "default_backend":
        if value not in _VALID_BACKENDS:
            raise ConfigStateError(
                f"invalid default_backend {value!r}; expected one of {list(_VALID_BACKENDS)}"
            )
        default_backend = cast(Backend, value)
    elif key == "email_pattern":
        email_pattern = value
    else:  # email_collision
        if value not in _VALID_COLLISION:
            raise ConfigStateError(
                f"invalid email_collision {value!r}; expected one of {list(_VALID_COLLISION)}"
            )
        email_collision = cast(CollisionMode, value)
    save(
        Config(
            schema_version=cfg.schema_version,
            domain=domain,
            default_backend=default_backend,
            email_pattern=email_pattern,
            email_collision=email_collision,
        )
    )
