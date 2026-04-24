"""Unit tests for zehut.config."""

from __future__ import annotations

import pytest

from zehut import config


@pytest.fixture
def tmp_zehut(tmp_path, monkeypatch):
    config_dir = tmp_path / "etc-zehut"
    state_dir = tmp_path / "var-lib-zehut"
    monkeypatch.setenv("ZEHUT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("ZEHUT_STATE_DIR", str(state_dir))
    config_dir.mkdir()
    state_dir.mkdir()
    return config_dir, state_dir


def test_default_config_values():
    cfg = config.Config.default(domain="agents.example.com", backend="system")
    assert cfg.schema_version == 1
    assert cfg.domain == "agents.example.com"
    assert cfg.default_backend == "system"
    assert cfg.email_pattern == "{name}"
    assert cfg.email_collision == "suffix"


def test_save_and_load_roundtrip(tmp_zehut):
    cfg = config.Config.default(domain="x.example.com", backend="subuser")
    config.save(cfg)
    loaded = config.load()
    assert loaded == cfg


def test_save_writes_expected_toml(tmp_zehut):
    config_dir, _ = tmp_zehut
    cfg = config.Config.default(domain="agents.example.com", backend="system")
    config.save(cfg)
    text = (config_dir / "config.toml").read_text()
    assert "schema_version = 1" in text
    assert 'domain = "agents.example.com"' in text
    assert 'backend = "system"' in text


def test_load_missing_raises_state_error(tmp_zehut):
    with pytest.raises(config.ConfigStateError) as exc:
        config.load()
    assert "not initialized" in str(exc.value).lower() or "missing" in str(exc.value).lower()


def test_load_wrong_schema_version_raises(tmp_zehut):
    config_dir, _ = tmp_zehut
    (config_dir / "config.toml").write_text(
        "schema_version = 2\n"
        '[defaults]\nbackend = "system"\n'
        '[email]\ndomain = "x.example.com"\npattern = "{name}"\ncollision = "suffix"\n'
    )
    with pytest.raises(config.ConfigStateError) as exc:
        config.load()
    assert "schema" in str(exc.value).lower()


def test_load_rejects_unknown_backend(tmp_zehut):
    config_dir, _ = tmp_zehut
    (config_dir / "config.toml").write_text(
        "schema_version = 1\n"
        '[defaults]\nbackend = "wat"\n'
        '[email]\ndomain = "x.example.com"\npattern = "{name}"\ncollision = "suffix"\n'
    )
    with pytest.raises(config.ConfigStateError):
        config.load()


def test_set_key_updates_value(tmp_zehut):
    cfg = config.Config.default(domain="x.example.com", backend="system")
    config.save(cfg)
    config.set_key("domain", "agents.new.com")
    reloaded = config.load()
    assert reloaded.domain == "agents.new.com"


def test_set_key_rejects_unknown_key(tmp_zehut):
    cfg = config.Config.default(domain="x.example.com", backend="system")
    config.save(cfg)
    with pytest.raises(config.ConfigStateError):
        config.set_key("not_a_real_key", "whatever")
