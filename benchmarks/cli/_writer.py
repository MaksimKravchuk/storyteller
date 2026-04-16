"""Shared stdout helper for the CLI package."""

from __future__ import annotations

import sys
from typing import Callable

Writer = Callable[[str], None]


def default_writer(line: str) -> None:
    """Write ``line`` followed by a newline to stdout."""
    sys.stdout.write("{0}\n".format(line))
