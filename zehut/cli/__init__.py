"""CLI entry point — Task 1 placeholder.

This module is fleshed out in Task 6 (parser + dispatch + error routing).
For now it exists so ``uv run zehut --version`` and ``python -m zehut`` work.
"""

from __future__ import annotations

import sys

from zehut import __version__


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args == ["--version"]:
        print(f"zehut {__version__}")
        return 0
    # Placeholder: anything else prints a stub message.
    # NOTE: Task 6 replaces this with argparse dispatch; unknown verbs will return EXIT_USER_ERROR (64).
    print("zehut CLI not yet implemented — see docs/superpowers/plans/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
