"""Unit tests for zehut.cli._errors."""

from __future__ import annotations

from zehut.cli import _errors


def test_exit_code_constants():
    assert _errors.EXIT_SUCCESS == 0
    assert _errors.EXIT_USER_ERROR == 64
    assert _errors.EXIT_STATE == 65
    assert _errors.EXIT_PRIVILEGE == 66
    assert _errors.EXIT_BACKEND == 67
    assert _errors.EXIT_CONFLICT == 68
    assert _errors.EXIT_INTERNAL == 70


def test_zehut_error_fields():
    err = _errors.ZehutError(
        code=_errors.EXIT_USER_ERROR,
        message="no such user",
        remediation="zehut user list",
    )
    assert err.code == 64
    assert err.message == "no such user"
    assert err.remediation == "zehut user list"
    assert isinstance(err, Exception)


def test_zehut_error_str_is_message():
    err = _errors.ZehutError(code=64, message="msg", remediation="r")
    assert str(err) == "msg"
