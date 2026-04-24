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


def test_full_logical_lifecycle(zehut_env):
    env = zehut_env

    rc = _run(env, "init", "--domain", "agents.example.com", "--default-backend", "logical")
    assert rc.returncode == 0, rc.stderr

    rc = _run(env, "user", "create", "alice", "--nick", "Ali")
    assert rc.returncode == 0, rc.stderr

    rc = _run(env, "--json", "user", "list")
    assert rc.returncode == 0
    payload = json.loads(rc.stdout.splitlines()[-1])
    assert payload[0]["name"] == "alice"

    rc = _run(env, "--json", "doctor")
    assert rc.returncode == 0
    doctor_payload = json.loads(rc.stdout.splitlines()[-1])
    statuses = {c["status"] for c in doctor_payload["checks"]}
    assert "FAIL" not in statuses, doctor_payload

    rc = _run(env, "user", "delete", "alice")
    assert rc.returncode == 0, rc.stderr
