"""Helpers for converting the NPC relationships field between DB and domain."""

from __future__ import annotations

import re

from models.relationship import Relationship, RelationshipKind

_HOSTILITY_KEYWORDS: frozenset[str] = frozenset(
    ("kill", "murder", "murderous", "harm", "wound", "enemy", "rival", "foe", "vendetta", "vengeance", "hostile"),
)
_HOSTILITY_RE = re.compile(
    r"(?:^|[^a-zA-Z])(?:{0})(?:[^a-zA-Z]|$)".format("|".join(_HOSTILITY_KEYWORDS)),
    re.IGNORECASE,
)


def _infer_kind(label: str) -> RelationshipKind:
    if _HOSTILITY_RE.search(label):
        return RelationshipKind.ENEMY
    return RelationshipKind.NEUTRAL


def _upcast_legacy(legacy: dict) -> list[Relationship]:
    rels: list[Relationship] = []
    for target_uuid, label in legacy.items():
        safe_label = label or ""
        kind = _infer_kind(safe_label)
        rels.append(
            Relationship(
                target_uuid=target_uuid,
                kind=kind,
                intensity=-3 if kind == RelationshipKind.ENEMY else 0,
                note=safe_label,
            )
        )
    return rels


def relationships_to_row(relationships: list[Relationship]) -> list[dict]:
    return [rel.model_dump(mode="json") for rel in relationships]


def row_to_relationships(payload: list | dict | None) -> list[Relationship]:
    if not payload:
        return []
    if isinstance(payload, dict):
        return _upcast_legacy(payload)
    return [Relationship.model_validate(entry) for entry in payload]
