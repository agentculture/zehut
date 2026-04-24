"""Smoke tests — prove the package is importable and --version works."""

from __future__ import annotations

import subprocess
import sys

import zehut


def test_version_attribute_exists() -> None:
    assert isinstance(zehut.__version__, str)
    assert zehut.__version__  # non-empty


def test_cli_version_flag() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "zehut", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "zehut" in result.stdout
