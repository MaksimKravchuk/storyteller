"""Loguru capture helpers for tests that assert warning side effects."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from loguru import logger


@contextmanager
def capture_warnings() -> Iterator[list[str]]:
    """Collect loguru WARNING messages emitted inside the with-block."""
    messages: list[str] = []
    sink_id = logger.add(messages.append, level="WARNING", format="{level} {message}")
    try:
        yield messages
    finally:
        logger.remove(sink_id)
