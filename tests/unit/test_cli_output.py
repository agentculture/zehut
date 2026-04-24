"""Unit tests for zehut.cli._output."""

from __future__ import annotations

import json

from zehut.cli import _errors, _output


def test_emit_result_text_prints_to_stdout(capsys):
    _output.emit_result("hello", json_mode=False)
    cap = capsys.readouterr()
    assert cap.out == "hello\n"
    assert cap.err == ""


def test_emit_result_json_prints_compact_json(capsys):
    _output.emit_result({"a": 1}, json_mode=True)
    cap = capsys.readouterr()
    assert json.loads(cap.out) == {"a": 1}
    assert cap.err == ""


def test_emit_diagnostic_goes_to_stderr(capsys):
    _output.emit_diagnostic("heads up", json_mode=False)
    cap = capsys.readouterr()
    assert cap.out == ""
    assert "heads up" in cap.err


def test_emit_error_text_format(capsys):
    err = _errors.ZehutError(code=64, message="no such user", remediation="zehut user list")
    _output.emit_error(err, json_mode=False)
    cap = capsys.readouterr()
    assert cap.out == ""
    assert "error: no such user" in cap.err
    assert "hint: zehut user list" in cap.err


def test_emit_error_json_shape(capsys):
    err = _errors.ZehutError(code=68, message="collision", remediation="pick a distinct --nick")
    _output.emit_error(err, json_mode=True)
    cap = capsys.readouterr()
    payload = json.loads(cap.err)
    assert payload == {
        "error": "collision",
        "code": 68,
        "hint": "pick a distinct --nick",
    }
