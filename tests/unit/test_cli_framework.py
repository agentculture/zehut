"""Unit tests for zehut.cli — parser, dispatch, main()."""

from __future__ import annotations

import json

from zehut import cli
from zehut.cli import _errors


def test_main_version_prints_and_returns_zero(capsys):
    rc = cli.main(["--version"])
    cap = capsys.readouterr()
    assert rc == 0
    assert "zehut" in cap.out


def test_main_no_args_prints_help_and_returns_zero(capsys):
    rc = cli.main([])
    cap = capsys.readouterr()
    assert rc == 0
    assert "usage:" in cap.out.lower() or "usage:" in cap.err.lower()


def test_main_unknown_subcommand_returns_user_error_text(capsys):
    rc = cli.main(["ghostverb"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_USER_ERROR
    assert "error:" in cap.err
    assert "hint:" in cap.err


def test_main_unknown_subcommand_returns_user_error_json(capsys):
    rc = cli.main(["--json", "ghostverb"])
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_USER_ERROR
    payload = json.loads(cap.err.splitlines()[-1])
    assert payload["code"] == _errors.EXIT_USER_ERROR
    assert "error" in payload
    assert "hint" in payload


def test_dispatch_wraps_unexpected_exception_as_internal(capsys):
    def boom(_args):
        raise RuntimeError("kaboom")

    import argparse

    ns = argparse.Namespace(func=boom, json=False)
    rc = cli._dispatch(ns)
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_INTERNAL
    assert "kaboom" in cap.err
    # Traceback must not leak.
    assert "Traceback" not in cap.err


def test_dispatch_handles_zehut_error(capsys):
    def raiser(_args):
        raise _errors.ZehutError(
            code=_errors.EXIT_CONFLICT, message="collision", remediation="retry"
        )

    import argparse

    ns = argparse.Namespace(func=raiser, json=False)
    rc = cli._dispatch(ns)
    cap = capsys.readouterr()
    assert rc == _errors.EXIT_CONFLICT
    assert "collision" in cap.err
    assert "retry" in cap.err
