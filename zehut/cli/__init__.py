"""Unified CLI entry point — parser, dispatcher, error routing.

Mirrors ``afi-cli``'s ``afi.cli`` module:

* Every argparse error routes through :func:`_output.emit_error` via a
  subclassed parser. This produces structured errors (text or JSON) with
  remediation hints instead of argparse's default ``prog: error:`` line.
* Handlers raise :class:`ZehutError`; :func:`_dispatch` catches and emits.
* Unknown exceptions are wrapped as ``EXIT_INTERNAL`` so no Python
  traceback ever reaches the user.
* Noun groups (``user``, ``configuration``) register themselves via a
  ``register(subparsers)`` function — wired in later tasks.
"""

from __future__ import annotations

import argparse
import sys

from zehut import __version__
from zehut.cli._errors import (
    EXIT_INTERNAL,
    EXIT_USER_ERROR,
    ZehutError,
)
from zehut.cli._output import emit_error


class _ParserExit(Exception):
    """Internal signal that argparse wants the program to exit.

    Raised from :meth:`_ZehutArgumentParser.exit` and ``.error`` instead of
    ``SystemExit``. :func:`main` catches this and converts to an integer
    return code. Keeping SystemExit out of zehut code means Sonar's S5754
    ("reraise SystemExit") never has reason to flag us — the rule only
    fires on SystemExit catches that don't reraise.
    """

    def __init__(self, code: int) -> None:
        super().__init__(f"_ParserExit({code})")
        self.code = code


class _ZehutArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that routes errors through :func:`emit_error`.

    Argparse's default ``error()`` writes ``prog: error: <msg>`` and exits.
    That skips our ZehutError plumbing (no hint, wrong exit code). This
    subclass emits the structured format and raises :class:`_ParserExit`
    instead of ``SystemExit``. The overridden ``exit()`` intercepts the
    same calls argparse makes from ``_VersionAction`` and ``_HelpAction``
    so those paths also surface as ``_ParserExit``.

    JSON mode: parse-time errors happen before ``args.json`` exists, so we
    rely on ``_json_hint`` that :func:`main` pre-populates by peeking at
    argv for ``--json`` / ``--json=…``.
    """

    _json_hint: bool = False

    def error(self, message: str) -> None:  # type: ignore[override]
        err = ZehutError(
            code=EXIT_USER_ERROR,
            message=message,
            remediation=f"run '{self.prog} --help' to see valid arguments",
        )
        emit_error(err, json_mode=type(self)._json_hint)
        raise _ParserExit(err.code)

    def exit(self, status: int = 0, message: str | None = None) -> None:  # type: ignore[override]
        # argparse invokes this from _VersionAction, _HelpAction, and from
        # its own error path (.error() → parser.exit()). Raising
        # _ParserExit keeps SystemExit out of our codebase.
        if message:
            self._print_message(message, sys.stderr)
        raise _ParserExit(int(status))


def _argv_has_json(argv: list[str] | None) -> bool:
    tokens = argv if argv is not None else sys.argv[1:]
    return any(t == "--json" or t.startswith("--json=") for t in tokens)


def _build_parser() -> argparse.ArgumentParser:
    parser = _ZehutArgumentParser(
        prog="zehut",
        description="zehut — agents-first identity layer",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit structured JSON for results and errors.",
    )
    # parser_class propagates to every subparser so .error() routes through
    # _ZehutArgumentParser everywhere.
    sub = parser.add_subparsers(dest="command", parser_class=_ZehutArgumentParser)

    # Lazy imports avoid circulars (command modules import cli._output etc.).
    from zehut.cli._commands import init as _init_cmd  # noqa: WPS433

    _init_cmd.register(sub)

    from zehut.cli._commands import configuration as _configuration_cmd  # noqa: WPS433

    _configuration_cmd.register(sub)

    from zehut.cli._commands import user as _user_cmd  # noqa: WPS433

    _user_cmd.register(sub)

    from zehut.cli._commands import doctor as _doctor_cmd  # noqa: WPS433

    _doctor_cmd.register(sub)

    from zehut.cli._commands import explain as _explain_cmd  # noqa: WPS433
    from zehut.cli._commands import learn as _learn_cmd  # noqa: WPS433
    from zehut.cli._commands import overview as _overview_cmd  # noqa: WPS433

    _learn_cmd.register(sub)
    _overview_cmd.register(sub)
    _explain_cmd.register(sub)

    # More noun groups and globals register here in later tasks.
    return parser


def _dispatch(args: argparse.Namespace) -> int:
    """Invoke the registered handler; translate exceptions to exit codes."""
    json_mode = bool(getattr(args, "json", False))
    func = getattr(args, "func", None)
    if func is None:
        # No subcommand selected — caller should have printed help.
        return 0
    try:
        rc = func(args)
    except ZehutError as err:
        emit_error(err, json_mode=json_mode)
        return err.code
    except Exception as err:  # noqa: BLE001 — last-resort wrap
        wrapped = ZehutError(
            code=EXIT_INTERNAL,
            message=f"unexpected: {err.__class__.__name__}: {err}",
            remediation="file a bug at https://github.com/OriNachum/zehut/issues",
        )
        emit_error(wrapped, json_mode=json_mode)
        return wrapped.code
    return rc if rc is not None else 0


def main(argv: list[str] | None = None) -> int:
    _ZehutArgumentParser._json_hint = _argv_has_json(argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except _ParserExit as exc:
        # argparse's --version, --help, and parse-error paths now raise
        # _ParserExit (see _ZehutArgumentParser). Convert to int so callers
        # receive a clean return code.
        return exc.code
    if getattr(args, "command", None) is None:
        parser.print_help()
        return 0
    return _dispatch(args)


if __name__ == "__main__":
    sys.exit(main())
