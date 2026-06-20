"""Fixed seven-axis values vector — the basis for emotional charge weighting.

Each axis is a signed weight in ``[-1.0, 1.0]``: positive means the NPC
prizes the value (and feels worse when it is violated), negative means
they reject it, ``0.0`` means indifferent. All axes default to ``0.0`` so
an NPC created without explicit values reacts on event-type base charge
alone. The deterministic deriver in :mod:`cast.emotional_memory` reads
these axes against each charge category's ``axis_signature`` (see
:mod:`knowledge.charge`) to colour per-witness valence at read time —
no LLM is involved. The axis names must match the signature keys in
:data:`knowledge.charge.AXIS_SIGNATURES`.
"""

from __future__ import annotations

from pydantic import Field

from models.base_model import StorytellerBase

_AXIS_FLOOR = float(-1)
_AXIS_CEIL = float(1)
_AXIS_FIELD = Field(default=float(0), ge=_AXIS_FLOOR, le=_AXIS_CEIL)


class ValuesVector(StorytellerBase):
    """A character's weighting of what they care about, across seven axes."""

    law: float = _AXIS_FIELD
    kinship: float = _AXIS_FIELD
    honor: float = _AXIS_FIELD
    wealth: float = _AXIS_FIELD
    faith: float = _AXIS_FIELD
    valor: float = _AXIS_FIELD
    tradition: float = _AXIS_FIELD
