"""Deterministic UUID helper for benchmark scenarios.

Mirrors ``tests/_uuid_helpers.make_uuid`` so benchmark fixtures can use
readable labels (``"marcus"``, ``"tavern"``) and still emit valid
``pydantic.UUID4`` values that compare equal across producer/consumer
boundaries within the same scenario.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from uuid import UUID

_UUID_BYTE_WIDTH = 16


@lru_cache(maxsize=None)
def make_uuid(label: str) -> UUID:
    """Return a deterministic ``UUID4`` derived from *label*. Cached."""
    digest = hashlib.sha1(label.encode()).digest()
    return UUID(bytes=digest[:_UUID_BYTE_WIDTH], version=4)
