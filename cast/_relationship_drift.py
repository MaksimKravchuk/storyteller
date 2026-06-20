"""Deterministic relationship drift from accumulated memory charge.

An NPC's :class:`~models.relationship.Relationship` toward every subject
it holds charged memories about is nudged by the accumulated, decayed,
values-coloured valence of those memories. The player is just one subject
among many. Only affective kinds drift; structural kinds (KIN/SUBORDINATE/
SUPERIOR) keep their kind. A dead-band gives hysteresis so a decaying
charge does not flap the kind across a band boundary read-to-read.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING
from uuid import UUID

from cast._mood_derivation import MOOD_SATURATION, memory_contribution
from models.relationship import Relationship, RelationshipKind

if TYPE_CHECKING:
    from knowledge.node import KnowledgeNode
    from models.npc_card import NPCCard

_INTENSITY_MIN = -3
_INTENSITY_MAX = 3
_DRIFT_SCALE = 3.0  # maps squashed per-subject valence (-1..1) onto ±3
_HYSTERESIS = 0.6  # min |target - stored| before stored intensity moves

_RIVAL_FLOOR = -1
_NEUTRAL_LEVEL = 0
_FRIEND_LEVEL = 1
_ENEMY_CEILING = -2

_AFFECTIVE_KINDS = frozenset(
    (
        RelationshipKind.NEUTRAL,
        RelationshipKind.FRIEND,
        RelationshipKind.ALLY,
        RelationshipKind.RIVAL,
        RelationshipKind.ENEMY,
    ),
)


def drift_relationships(
    npc: NPCCard,
    memories: list[KnowledgeNode],
    now: float,
    *,
    turn: int | None = None,
) -> None:
    """Nudge the NPC's relationship toward every subject of its charged memories."""
    for subject_id, valence_sum in _net_valence_by_subject(npc, memories, now).items():
        relationship = _ensure_relationship(npc, subject_id, turn)
        _apply_intensity(relationship, _intensity_target(valence_sum))


def _net_valence_by_subject(npc: NPCCard, memories: list[KnowledgeNode], now: float) -> dict[UUID, float]:
    totals: dict[UUID, float] = defaultdict(float)
    for memory in memories:
        subject_id = memory.subject_id
        if subject_id is None or subject_id == npc.uuid:
            continue
        totals[subject_id] += memory_contribution(npc.values_vector, memory, now)
    return totals


def _intensity_target(valence_sum: float) -> float:
    return math.tanh(valence_sum / MOOD_SATURATION) * _DRIFT_SCALE


def _ensure_relationship(npc: NPCCard, subject_id: UUID, turn: int | None) -> Relationship:
    target_uuid = str(subject_id)
    for relationship in npc.relationships:
        if relationship.target_uuid == target_uuid:
            return relationship
    created = Relationship(
        target_uuid=target_uuid,
        kind=RelationshipKind.NEUTRAL,
        intensity=0,
        established_turn=turn,
    )
    npc.relationships.append(created)
    return created


def _apply_intensity(relationship: Relationship, target: float) -> None:
    if abs(target - relationship.intensity) < _HYSTERESIS:
        return
    new_intensity = max(_INTENSITY_MIN, min(_INTENSITY_MAX, round(target)))
    relationship.intensity = new_intensity
    relationship.kind = _kind_for_intensity(relationship.kind, new_intensity)


def _kind_for_intensity(current_kind: RelationshipKind, intensity: int) -> RelationshipKind:
    if current_kind not in _AFFECTIVE_KINDS:
        return current_kind
    return _affective_band(intensity)


def _affective_band(intensity: int) -> RelationshipKind:
    if intensity <= _ENEMY_CEILING:
        return RelationshipKind.ENEMY
    if intensity == _RIVAL_FLOOR:
        return RelationshipKind.RIVAL
    if intensity == _NEUTRAL_LEVEL:
        return RelationshipKind.NEUTRAL
    if intensity == _FRIEND_LEVEL:
        return RelationshipKind.FRIEND
    return RelationshipKind.ALLY
