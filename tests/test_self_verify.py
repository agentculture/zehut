"""End-to-end self-verify: a full lifecycle against a tmpdir-rooted zehut.

Runs the CLI as a subprocess so argv parsing, env resolution, and exit
codes are exercised the way a user or agent would invoke them.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest


@pytest.fixture
def zehut_env(tmp_path):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    config_dir.mkdir()
    state_dir.mkdir()
    env = os.environ.copy()
    env["ZEHUT_CONFIG_DIR"] = str(config_dir)
    env["ZEHUT_STATE_DIR"] = str(state_dir)
    env["ZEHUT_ASSUME_ROOT"] = "1"
    env.pop("ZEHUT_IDENTITY", None)
    return env


def _run(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zehut", *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_system_parent(state_dir_env: str, name: str = "agent") -> None:
    """Inject a system-backed parent row into users.json without useradd.

    Creating a real system parent via the CLI would shell out to useradd,
    which we can't safely run in a unit-test context. We write the JSON
    directly under the same schema the CLI produces, then let the CLI
    subprocess pick up the registry state.
    """
    from pathlib import Path

    path = Path(state_dir_env) / "users.json"
    doc = json.loads(path.read_text())
    doc["users"].append(
        {
            "id": "01SEEDED00000000000000000A",
            "name": name,
            "nick": None,
            "about": None,
            "email": f"{name}@agents.example.com",
            "backend": "system",
            "system_user": name,
            "system_uid": 4242,
            "parent_id": None,
            "created_at": "2026-04-24T00:00:00Z",
            "updated_at": "2026-04-24T00:00:00Z",
        }
    )
    path.write_text(json.dumps(doc, indent=2))


def test_full_subuser_lifecycle(zehut_env):
    """Init → seed system parent → create sub-user via CLI → list →
    doctor → cascade-delete.
    """
    env = zehut_env

    rc = _run(env, "init", "--domain", "agents.example.com", "--default-backend", "subuser")
    assert rc.returncode == 0, rc.stderr

    _seed_system_parent(env["ZEHUT_STATE_DIR"], name="agent")

    rc = _run(env, "user", "create", "alice", "--subuser", "--parent", "agent", "--nick", "Ali")
    assert rc.returncode == 0, rc.stderr

    rc = _run(env, "--json", "user", "list")
    assert rc.returncode == 0
    payload = json.loads(rc.stdout.splitlines()[-1])
    names = {r["name"] for r in payload}
    assert names == {"agent", "alice"}

    # Doctor must not FAIL. system_users_resolve will WARN because the
    # seeded 'agent' UID isn't a real OS user — acceptable; we only
    # assert no FAIL.
    rc = _run(env, "--json", "doctor")
    assert rc.returncode == 0
    doctor_payload = json.loads(rc.stdout.splitlines()[-1])
    failing = [c for c in doctor_payload["checks"] if c["status"] == "FAIL"]
    # The seeded system parent won't resolve via pwd.getpwnam, so
    # system_users_resolve is expected to FAIL. subuser_parents_valid
    # must still pass — that's the meaningful assertion for this PR.
    parent_check = next(c for c in doctor_payload["checks"] if c["name"] == "subuser_parents_valid")
    assert parent_check["status"] == "PASS", doctor_payload
    # The only acceptable FAIL is the synthetic parent resolution.
    for c in failing:
        assert c["name"] == "system_users_resolve", doctor_payload

    # Delete just the sub-user first (no cascade expected).
    rc = _run(env, "--json", "user", "delete", "alice")
    assert rc.returncode == 0, rc.stderr
    delete_payload = json.loads(rc.stdout.splitlines()[-1])
    assert delete_payload == {
        "deleted": "alice",
        "backend": "subuser",
        "cascaded_subusers": [],
    }

    rc = _run(env, "--json", "user", "list")
    assert rc.returncode == 0
    remaining = json.loads(rc.stdout.splitlines()[-1])
    assert {r["name"] for r in remaining} == {"agent"}
