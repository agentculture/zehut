"""Unit tests for the agent-first globals (learn, overview, explain)."""

from __future__ import annotations

import json

import pytest

from zehut import cli
from zehut.cli import _errors


@pytest.fixture
def tmp_zehut(tmp_path, monkeypatch):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    monkeypatch.setattr("zehut.privilege.os.geteuid", lambda: 0)
    cli.main(["init", "--domain", "agents.example.com", "--default-backend", "logical"])
    cli.main(["user", "create", "alice", "--nick", "Ali"])
    return config_dir, state_dir


def test_learn_emits_markdown_with_frontmatter(tmp_zehut, capsys):
    rc = cli.main(["learn"])
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out.startswith("---\n")
    assert "name:" in cap.out
    assert "zehut user" in cap.out


def test_overview_json_shape(tmp_zehut, capsys):
    rc = cli.main(["--json", "overview"])
    cap = capsys.readouterr()
    assert rc == 0
    payload = json.loads(cap.out.splitlines()[-1])
    assert "config" in payload
    assert "users" in payload
    assert payload["config"]["domain"] == "agents.example.com"
    assert payload["users"][0]["name"] == "alice"


def test_overview_text(tmp_zehut, capsys):
    rc = cli.main(["overview"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "agents.example.com" in cap.out
    assert "alice" in cap.out


def test_explain_known_topic(tmp_zehut, capsys):
    rc = cli.main(["explain", "user"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "user" in cap.out.lower()


def test_explain_unknown_topic(tmp_zehut, capsys):
    rc = cli.main(["explain", "frobnicate"])
    assert rc == _errors.EXIT_USER_ERROR
