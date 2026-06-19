"""Deterministic mood derivation from decayed, values-coloured memory charge.

Pure synchronous math, no LLM. The aggregate of an NPC's decayed,
per-witness-valenced personal-memory charges is squashed with ``tanh``
and mapped onto a label drawn from the hostility intensity ladder
(:data:`cast.hostility._MOOD_INTENSITY`), so the same label feeds both
the retaliation mechanic and the Actor prose prompt.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from knowledge import charge as charge_presets

if TYPE_CHECKING:
    from knowledge.node import KnowledgeNode
    from models.npc_card import NPCCard
    from models.values_vector import ValuesVector

_NEUTRAL_MOOD = "neutral"
# tanh scale squashing a raw charge aggregate into (-1, 1). Shared by the
# relationship-drift module so mood and drift stay on the same curve.
MOOD_SATURATION = 2.0
_FLOAT_ZERO = float(0)

# Negative-aggregate ladder, strongest first: a squashed score at or below
# a threshold maps to that hostile label. Cuts are even 0.125 steps so the
# seven hostile rungs of ``_MOOD_INTENSITY`` are evenly reachable.
_NEGATIVE_BANDS: tuple[tuple[float, str], ...] = (
    (-0.875, "enraged"),
    (-0.75, "furious"),
    (-0.625, "hostile"),
    (-0.5, "angry"),
    (-0.375, "threatened"),
    (-0.25, "irritated"),
    (-0.125, "suspicious"),
)
_HAPPY_THRESHOLD = 0.5
_CONTENT_THRESHOLD = 0.125


def derive_mood(npc: NPCCard, memories: list[KnowledgeNode], now: float) -> str:
    """Map the NPC's decayed, values-coloured memory charge onto a mood label."""
    return _mood_label(_mood_aggregate(npc.values_vector, memories, now))


def has_emotional_signal(memories: list[KnowledgeNode], now: float) -> bool:
    """Report whether any memory still carries non-decayed emotional intensity."""
    return any(
        charge_presets.decayed_intensity(memory.charge_intensity, memory.timestamp, now) > 0 for memory in memories
    )


def memory_contribution(value_weights: ValuesVector, memory: KnowledgeNode, now: float) -> float:
    """Salience-weighted, decayed, values-coloured signed contribution of one memory."""
    decayed = charge_presets.decayed_intensity(memory.charge_intensity, memory.timestamp, now)
    if decayed == 0:
        return _FLOAT_ZERO
    witness_valence = charge_presets.values_adjusted_valence(memory.valence, memory.charge_category, value_weights)
    return memory.salience * decayed * witness_valence


def _mood_aggregate(value_weights: ValuesVector, memories: list[KnowledgeNode], now: float) -> float:
    total = sum(memory_contribution(value_weights, memory, now) for memory in memories)
    return math.tanh(total / MOOD_SATURATION)


def _mood_label(score: float) -> str:
    for threshold, label in _NEGATIVE_BANDS:
        if score <= threshold:
            return label
    if score >= _HAPPY_THRESHOLD:
        return "happy"
    if score >= _CONTENT_THRESHOLD:
        return "content"
    return _NEUTRAL_MOOD
