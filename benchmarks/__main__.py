"""Entry point so ``python -m benchmarks ...`` dispatches to the CLI."""

from __future__ import annotations

import sys

from benchmarks.cli._main import main

if __name__ == "__main__":
    sys.exit(main())
