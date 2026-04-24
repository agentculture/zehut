"""Unit tests for zehut.users — registry CRUD + email generation."""

from __future__ import annotations

import json

import pytest

from zehut import config, fs, users
from zehut.backend.logical import LogicalBackend
from zehut.cli._errors import EXIT_CONFLICT, EXIT_STATE, EXIT_USER_ERROR, ZehutError


@pytest.fixture
def tmp_zehut(tmp_path, monkeypatch):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    cfg = config.Config.default(domain="agents.example.com", backend="logical")
    config.save(cfg)
    users.init_registry()
    return config_dir, state_dir


# --- email generation ---------------------------------------------------------


def test_render_email_single_token(tmp_zehut):
    assert users.render_email("{name}", name="alice", nick="", domain="x.com") == "alice@x.com"


def test_render_email_nick_fallback_operator(tmp_zehut):
    # Nick present → use it.
    assert (
        users.render_email("{nick|name}", name="alice", nick="ali", domain="x.com") == "ali@x.com"
    )
    # Nick empty → fall back to name.
    assert users.render_email("{nick|name}", name="alice", nick="", domain="x.com") == "alice@x.com"


def test_render_email_id_short_token(tmp_zehut):
    email = users.render_email(
        "{id-short}", name="alice", nick="", domain="x.com", id_short="01HYA9ZZ"
    )
    assert email == "01HYA9ZZ@x.com"


def test_render_email_empty_result_raises(tmp_zehut):
    with pytest.raises(ZehutError) as exc:
        users.render_email("{nick}", name="alice", nick="", domain="x.com")
    assert exc.value.code == EXIT_USER_ERROR


# --- registry CRUD ------------------------------------------------------------


def test_init_registry_creates_empty_file(tmp_zehut):
    _, state_dir = tmp_zehut
    path = state_dir / "users.json"
    assert path.exists()
    assert fs.read_json(path) == {"schema_version": 1, "users": []}


def test_add_then_list(tmp_zehut):
    be = LogicalBackend()
    rec = users.add(name="alice", nick="Ali", about="qa", backend_name="logical", backend=be)
    assert rec.name == "alice"
    assert rec.backend == "logical"
    assert rec.email.endswith("@agents.example.com")
    lst = users.list_all()
    assert len(lst) == 1
    assert lst[0].name == "alice"


def test_add_duplicate_name_raises_conflict(tmp_zehut):
    be = LogicalBackend()
    users.add(name="alice", nick=None, about=None, backend_name="logical", backend=be)
    with pytest.raises(ZehutError) as exc:
        users.add(name="alice", nick=None, about=None, backend_name="logical", backend=be)
    assert exc.value.code == EXIT_CONFLICT


def test_add_email_collision_appends_suffix(tmp_zehut, monkeypatch):
    # Force every render to produce "ali@..." so collisions happen.
    monkeypatch.setattr(users, "render_email", lambda pattern, **kw: f"ali@{kw['domain']}")
    be = LogicalBackend()
    r1 = users.add(name="alice", nick="Ali", about=None, backend_name="logical", backend=be)
    r2 = users.add(name="alice2", nick="Ali", about=None, backend_name="logical", backend=be)
    assert r1.email == "ali@agents.example.com"
    assert r2.email == "ali-2@agents.example.com"


def test_get_returns_record(tmp_zehut):
    be = LogicalBackend()
    users.add(name="alice", nick=None, about=None, backend_name="logical", backend=be)
    rec = users.get("alice")
    assert rec.name == "alice"


def test_get_missing_raises_user_error(tmp_zehut):
    with pytest.raises(ZehutError) as exc:
        users.get("ghost")
    assert exc.value.code == EXIT_USER_ERROR


def test_update_sets_nick_and_about(tmp_zehut):
    be = LogicalBackend()
    users.add(name="alice", nick=None, about=None, backend_name="logical", backend=be)
    users.update("alice", nick="Ali", about="qa agent")
    rec = users.get("alice")
    assert rec.nick == "Ali"
    assert rec.about == "qa agent"


def test_update_rejects_immutable_keys(tmp_zehut):
    be = LogicalBackend()
    users.add(name="alice", nick=None, about=None, backend_name="logical", backend=be)
    with pytest.raises(ZehutError) as exc:
        users.update("alice", email="other@x.com")
    assert exc.value.code == EXIT_USER_ERROR


def test_remove_drops_record(tmp_zehut):
    be = LogicalBackend()
    users.add(name="alice", nick=None, about=None, backend_name="logical", backend=be)
    users.remove("alice", backend=be, keep_home=False)
    assert users.list_all() == []


def test_registry_load_rejects_wrong_schema(tmp_zehut):
    _, state_dir = tmp_zehut
    fs.atomic_write_text(
        state_dir / "users.json",
        json.dumps({"schema_version": 2, "users": []}),
        mode=0o644,
    )
    with pytest.raises(ZehutError) as exc:
        users.list_all()
    assert exc.value.code == EXIT_STATE


def test_ulid_is_26_crockford_chars(tmp_zehut):
    u = users._generate_ulid()
    assert len(u) == 26
    assert set(u).issubset(set("0123456789ABCDEFGHJKMNPQRSTVWXYZ"))


# --- ambient_name -------------------------------------------------------------


def test_ambient_name_none_when_no_match(tmp_zehut, monkeypatch):
    # No records; OS user doesn't match; env var unset.
    monkeypatch.delenv("ZEHUT_IDENTITY", raising=False)
    assert users.ambient_name() is None


def test_ambient_name_matches_system_backed_os_user(tmp_zehut, monkeypatch):
    import types

    be = LogicalBackend()
    users.add(name="alice", nick=None, about=None, backend_name="logical", backend=be)
    # Seed a system-backed record by poking the registry directly.
    doc = users._load_raw_unlocked()
    doc["users"].append(
        {
            "id": "01FAKE0000000000000000000A",
            "name": "bob",
            "nick": None,
            "about": None,
            "email": "bob@agents.example.com",
            "backend": "system",
            "system_user": "bob",
            "system_uid": 1234,
            "created_at": "2026-04-24T00:00:00Z",
            "updated_at": "2026-04-24T00:00:00Z",
        }
    )
    users._save_raw(doc)
    monkeypatch.setattr(
        users.pwd,
        "getpwuid",
        lambda uid: types.SimpleNamespace(pw_name="bob", pw_uid=1234),
    )
    monkeypatch.delenv("ZEHUT_IDENTITY", raising=False)
    assert users.ambient_name() == "bob"


def test_ambient_name_env_var_fallback(tmp_zehut, monkeypatch):
    import types

    be = LogicalBackend()
    users.add(name="alice", nick=None, about=None, backend_name="logical", backend=be)
    # OS user does not match any zehut record.
    monkeypatch.setattr(
        users.pwd,
        "getpwuid",
        lambda uid: types.SimpleNamespace(pw_name="nobody", pw_uid=65534),
    )
    monkeypatch.setenv("ZEHUT_IDENTITY", "alice")
    assert users.ambient_name() == "alice"
