"""Allow ``python -m zehut`` to reach the CLI entry point."""

from __future__ import annotations

import sys

from zehut.cli import main

if __name__ == "__main__":
    sys.exit(main())
