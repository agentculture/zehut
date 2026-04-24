"""Unit tests for zehut.users — registry CRUD + email generation."""

from __future__ import annotations

import json

import pytest

from zehut import config, fs, users
from zehut.backend.subuser import SubUserBackend
from zehut.cli._errors import EXIT_CONFLICT, EXIT_STATE, EXIT_USER_ERROR, ZehutError


@pytest.fixture
def tmp_zehut(tmp_path, monkeypatch):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    cfg = config.Config.default(domain="agents.example.com", backend="subuser")
    config.save(cfg)
    users.init_registry()
    return config_dir, state_dir


def _seed_system_parent(name: str = "parent", uid: int = 1234) -> str:
    """Inject a system-backed parent row without running useradd.

    Returns the seeded parent's ULID so tests can assert parent_id linkage
    when needed.
    """
    doc = users._load_raw_unlocked()
    parent_id = users._generate_ulid()
    doc["users"].append(
        {
            "id": parent_id,
            "name": name,
            "nick": None,
            "about": None,
            "email": f"{name}@agents.example.com",
            "backend": "system",
            "system_user": name,
            "system_uid": uid,
            "parent_id": None,
            "created_at": "2026-04-24T00:00:00Z",
            "updated_at": "2026-04-24T00:00:00Z",
        }
    )
    users._save_raw(doc)
    return parent_id


def _add_subuser(name: str, *, parent: str = "parent", **kw):
    return users.add(
        name=name,
        nick=kw.get("nick"),
        about=kw.get("about"),
        backend_name="subuser",
        backend=SubUserBackend(),
        parent_name=parent,
    )


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
    assert fs.read_json(path) == {"schema_version": 2, "users": []}


def test_add_subuser_then_list(tmp_zehut):
    parent_id = _seed_system_parent()
    rec = _add_subuser("alice", nick="Ali", about="qa")
    assert rec.name == "alice"
    assert rec.backend == "subuser"
    assert rec.parent_id == parent_id
    assert rec.email.endswith("@agents.example.com")
    lst = users.list_all()
    assert len(lst) == 2  # parent + subuser
    names = {r.name for r in lst}
    assert names == {"parent", "alice"}


def test_add_duplicate_name_raises_conflict(tmp_zehut):
    _seed_system_parent()
    _add_subuser("alice")
    with pytest.raises(ZehutError) as exc:
        _add_subuser("alice")
    assert exc.value.code == EXIT_CONFLICT


def test_add_subuser_without_parent_raises(tmp_zehut):
    with pytest.raises(ZehutError) as exc:
        users.add(
            name="alice",
            nick=None,
            about=None,
            backend_name="subuser",
            backend=SubUserBackend(),
            parent_name=None,
        )
    assert exc.value.code == EXIT_USER_ERROR
    assert "--parent" in exc.value.message


def test_add_subuser_with_missing_parent_raises(tmp_zehut):
    with pytest.raises(ZehutError) as exc:
        _add_subuser("alice", parent="ghost")
    assert exc.value.code == EXIT_USER_ERROR


def test_add_subuser_with_subuser_parent_raises(tmp_zehut):
    # Attempting to use a sub-user as parent trips the "parent must be
    # system-backed" check — which is the constraint that enforces the
    # flat hierarchy at creation time.
    _seed_system_parent()
    _add_subuser("bot1")
    with pytest.raises(ZehutError) as exc:
        _add_subuser("bot2", parent="bot1")
    assert exc.value.code == EXIT_USER_ERROR
    assert "system-backed" in exc.value.message


def test_add_subuser_rejects_parent_with_its_own_parent_id(tmp_zehut):
    # Belt-and-suspenders: if users.json has been tampered with so that
    # a system-backed user has a non-null parent_id, creation must still
    # refuse to use it as a parent (flat-hierarchy invariant).
    _seed_system_parent("root")
    doc = users._load_raw_unlocked()
    # Manually promote a second "system" entry to sub-of-root.
    tainted_id = users._generate_ulid()
    doc["users"].append(
        {
            "id": tainted_id,
            "name": "tainted",
            "nick": None,
            "about": None,
            "email": "tainted@agents.example.com",
            "backend": "system",
            "system_user": "tainted",
            "system_uid": 9999,
            "parent_id": doc["users"][0]["id"],
            "created_at": "2026-04-24T00:00:00Z",
            "updated_at": "2026-04-24T00:00:00Z",
        }
    )
    users._save_raw(doc)
    with pytest.raises(ZehutError) as exc:
        _add_subuser("bot", parent="tainted")
    assert exc.value.code == EXIT_USER_ERROR
    assert "flat" in exc.value.message


def test_add_parent_rejected_for_non_subuser(tmp_zehut, monkeypatch):
    # Passing --parent with any non-subuser backend must be rejected.
    # We use the subuser backend as the "wrong" backend_name label since
    # no system-backed creation in a unit test would be safe, but the
    # validator runs before any backend call.
    _seed_system_parent()
    with pytest.raises(ZehutError) as exc:
        users.add(
            name="alice",
            nick=None,
            about=None,
            backend_name="system",
            backend=SubUserBackend(),
            parent_name="parent",
        )
    assert exc.value.code == EXIT_USER_ERROR
    assert "--parent" in exc.value.message


def test_add_email_collision_appends_suffix(tmp_zehut, monkeypatch):
    # Force every render to produce "ali@..." so collisions happen.
    monkeypatch.setattr(users, "render_email", lambda pattern, **kw: f"ali@{kw['domain']}")
    _seed_system_parent()
    r1 = _add_subuser("alice", nick="Ali")
    r2 = _add_subuser("alice2", nick="Ali")
    # One of them collides with "parent@..."; the patched render always
    # returns "ali@...", so the second subuser gets the suffix.
    assert r1.email == "ali@agents.example.com"
    assert r2.email == "ali-2@agents.example.com"


def test_get_returns_record(tmp_zehut):
    _seed_system_parent()
    _add_subuser("alice")
    rec = users.get("alice")
    assert rec.name == "alice"


def test_get_missing_raises_user_error(tmp_zehut):
    with pytest.raises(ZehutError) as exc:
        users.get("ghost")
    assert exc.value.code == EXIT_USER_ERROR


def test_update_sets_nick_and_about(tmp_zehut):
    _seed_system_parent()
    _add_subuser("alice")
    users.update("alice", nick="Ali", about="qa agent")
    rec = users.get("alice")
    assert rec.nick == "Ali"
    assert rec.about == "qa agent"


def test_update_rejects_immutable_keys(tmp_zehut):
    _seed_system_parent()
    _add_subuser("alice")
    with pytest.raises(ZehutError) as exc:
        users.update("alice", email="other@x.com")
    assert exc.value.code == EXIT_USER_ERROR


def test_remove_drops_record(tmp_zehut):
    _seed_system_parent()
    _add_subuser("alice")
    cascaded = users.remove("alice", backend=SubUserBackend(), keep_home=False)
    assert cascaded == []
    remaining = {r.name for r in users.list_all()}
    assert remaining == {"parent"}


def test_remove_cascade_deletes_subusers(tmp_zehut, monkeypatch):
    """Deleting a system-backed parent cascade-deletes its sub-users."""
    _seed_system_parent("agent")
    _seed_system_parent("other")  # unrelated parent, must not be touched
    _add_subuser("bot1", parent="agent")
    _add_subuser("bot2", parent="agent")
    _add_subuser("bot-other", parent="other")

    # Stub the system backend's deprovision so we don't actually try to
    # call userdel. A SubUserBackend deprovision is a no-op and safe to
    # use here as a stand-in since remove() only calls it against the
    # named 'agent' target.
    cascaded = users.remove("agent", backend=SubUserBackend(), keep_home=False)

    assert sorted(cascaded) == ["bot1", "bot2"]
    remaining = {r.name for r in users.list_all()}
    assert remaining == {"other", "bot-other"}


def test_remove_does_not_cascade_non_subuser_children(tmp_zehut):
    """Cascade is scoped to `backend == "subuser"`.

    Guard against a tampered registry: a system-backed record that has
    been hand-edited to carry a ``parent_id`` MUST NOT be swept away by
    the cascade — doing so would leave an orphan OS account. The
    tampered row is surfaced by ``doctor.subuser_parents_valid``
    instead.
    """
    parent_id = _seed_system_parent("agent")
    # Genuine sub-user under agent — this one should be cascaded.
    _add_subuser("legit_bot", parent="agent")
    # Tamper: a *system-backed* row whose parent_id points at agent.
    doc = users._load_raw_unlocked()
    doc["users"].append(
        {
            "id": users._generate_ulid(),
            "name": "tampered_sys",
            "nick": None,
            "about": None,
            "email": "tampered_sys@agents.example.com",
            "backend": "system",
            "system_user": "tampered_sys",
            "system_uid": 8888,
            "parent_id": parent_id,
            "created_at": "2026-04-24T00:00:00Z",
            "updated_at": "2026-04-24T00:00:00Z",
        }
    )
    users._save_raw(doc)

    cascaded = users.remove("agent", backend=SubUserBackend(), keep_home=False)
    assert cascaded == ["legit_bot"]
    remaining = {r.name for r in users.list_all()}
    # The tampered system row must survive — it's still present, now
    # with a dangling parent_id that doctor will report as FAIL. The
    # user has to delete it explicitly so its OS backend runs.
    assert remaining == {"tampered_sys"}


def test_registry_load_rejects_wrong_schema(tmp_zehut):
    _, state_dir = tmp_zehut
    fs.atomic_write_text(
        state_dir / "users.json",
        json.dumps({"schema_version": 99, "users": []}),
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

    _seed_system_parent("bob", uid=1234)
    _add_subuser("alice", parent="bob")
    monkeypatch.setattr(
        users.pwd,
        "getpwuid",
        lambda uid: types.SimpleNamespace(pw_name="bob", pw_uid=1234),
    )
    monkeypatch.delenv("ZEHUT_IDENTITY", raising=False)
    assert users.ambient_name() == "bob"


def test_ambient_name_env_var_fallback(tmp_zehut, monkeypatch):
    import types

    _seed_system_parent()
    _add_subuser("alice")
    # OS user does not match any zehut record.
    monkeypatch.setattr(
        users.pwd,
        "getpwuid",
        lambda uid: types.SimpleNamespace(pw_name="nobody", pw_uid=65534),
    )
    monkeypatch.setenv("ZEHUT_IDENTITY", "alice")
    assert users.ambient_name() == "alice"
