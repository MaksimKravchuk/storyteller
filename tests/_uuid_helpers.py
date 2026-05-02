"""Test helpers that produce valid UUID4 values from readable labels.

KER-44 made every domain ``uuid`` field a real ``pydantic.UUID4`` rather
than a free-form string. Hundreds of pre-existing tests carry literals
like ``npc.uuid = "npc-brutus"`` that are not valid UUIDs and would now
fail validation. Rewriting them to ``uuid.uuid4()`` would lose the
readable label that helped diagnose test failures; rewriting them to a
fixed canonical UUID per label is what this helper provides.

``make_uuid(label)`` returns a deterministic ``uuid.UUID`` derived from
the label by hashing — the same label always produces the same UUID,
so equality assertions across producer / consumer boundaries continue
to work without threading a fixture-built UUID through every fake.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from uuid import UUID

# Number of bytes a v4 UUID consumes from the SHA-1 digest. Pulled out
# as a named constant so the (otherwise magic) slice stays readable
# under the project's WPS432 rule.
_UUID_BYTES = 16


@lru_cache(maxsize=None)
def make_uuid(label: str) -> UUID:
    """Return a deterministic ``UUID4`` derived from *label*.

    The version + RFC 4122 variant nibbles are rewritten by
    ``UUID(bytes=..., version=4)`` so the result is a well-formed v4
    UUID that ``pydantic.UUID4`` accepts. Cached so repeat lookups in
    fixtures don't re-hash on every call.
    """
    digest = hashlib.sha1(label.encode()).digest()
    return UUID(bytes=digest[:_UUID_BYTES], version=4)
