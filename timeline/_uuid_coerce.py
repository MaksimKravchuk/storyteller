"""Coerce JSON-roundtripped uuid values into native ``uuid.UUID`` instances.

Effect payloads (``EventEffect.effect_data``) cross the JSON boundary as
``dict[str, Any]``, so any uuid fields arrive as strings. The rest of
the engine expects native ``UUID`` so this helper is the single
narrowing point.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


def coerce_uuid(raw: Any) -> UUID | None:
    """Return ``raw`` as a ``UUID`` (or ``None`` for missing/empty input).

    Asymmetric on purpose: ``None`` and ``""`` are "field omitted" (the
    common case for optional ``effect_data`` keys) and flow through as
    ``None``. Any other non-empty unparseable input raises
    ``ValueError`` from :class:`uuid.UUID` — that signals serialized
    state corruption and should fail loudly rather than silently
    collapse to ``None``.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, UUID):
        return raw
    return UUID(str(raw))
