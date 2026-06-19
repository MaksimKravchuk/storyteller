"""KnowledgeNode ↔ DB row converters."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from db.converters._columns import COL_GAME_STATE_ID, COL_ID, COL_LOCATION_ID, COL_SCOPE, COL_TAGS
from db.converters._uuid_text import uuid_to_text
from knowledge import salience as salience_presets
from knowledge.node import CanonSource, EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource

_COL_CANON = "canon"
_COL_CHARGE_CATEGORY = "charge_category"
_COL_CHARGE_INTENSITY = "charge_intensity"
_COL_EDGE_TYPE = "edge_type"
_COL_FROM_NODE_ID = "from_node_id"
_COL_METADATA = "metadata_"
_COL_SALIENCE = "salience"
_COL_SUBJECT_ID = "subject_id"
_COL_TO_NODE_ID = "to_node_id"
_COL_VALENCE = "valence"
_DEFAULT_CANON = CanonSource.HISTORICAL.value
_DEFAULT_CHARGE = float(0)
_DEFAULT_CHARGE_CATEGORY = ""


def knowledge_node_to_row(node: KnowledgeNode, game_state_id: str) -> dict:
    return {
        COL_ID: node.uuid,
        COL_GAME_STATE_ID: game_state_id,
        "content": node.text,
        COL_SCOPE: node.scope.name.lower(),
        "source": node.source.value,
        _COL_CANON: node.canon.value,
        "required_education": node.required_education,
        COL_TAGS: node.tags,
        COL_LOCATION_ID: uuid_to_text(node.location_id),
        "timestamp": node.timestamp,
        _COL_SALIENCE: node.salience,
        _COL_VALENCE: node.valence,
        _COL_CHARGE_INTENSITY: node.charge_intensity,
        _COL_CHARGE_CATEGORY: node.charge_category,
        "subject": node.subject,
        "object": node.object,
        "action": node.action,
        "outcome": node.outcome,
        _COL_SUBJECT_ID: uuid_to_text(node.subject_id),
    }


def row_to_knowledge_node(row) -> KnowledgeNode:
    return KnowledgeNode(
        uuid=row[COL_ID],
        text=row["content"],
        scope=KnowledgeScope[row[COL_SCOPE].upper()],
        source=KnowledgeSource(row["source"]),
        canon=CanonSource(row.get(_COL_CANON, _DEFAULT_CANON)),
        required_education=row["required_education"],
        tags=row[COL_TAGS],
        location_id=row[COL_LOCATION_ID],
        timestamp=row["timestamp"],
        salience=row.get(_COL_SALIENCE, salience_presets.DEFAULT),
        valence=row.get(_COL_VALENCE, _DEFAULT_CHARGE),
        charge_intensity=row.get(_COL_CHARGE_INTENSITY, _DEFAULT_CHARGE),
        charge_category=row.get(_COL_CHARGE_CATEGORY, _DEFAULT_CHARGE_CATEGORY),
        subject=row.get("subject"),
        object=row.get("object"),
        action=row.get("action"),
        outcome=row.get("outcome"),
        subject_id=row.get(_COL_SUBJECT_ID),
    )


def knowledge_edge_to_row(
    game_state_id: str,
    from_node_id: UUID,
    to_node_id: UUID,
    edge_type: EdgeType,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Convert one in-memory graph edge to a DB row."""
    return {
        COL_GAME_STATE_ID: game_state_id,
        _COL_FROM_NODE_ID: from_node_id,
        _COL_TO_NODE_ID: to_node_id,
        _COL_EDGE_TYPE: edge_type.value,
        _COL_METADATA: edge_metadata_to_json(metadata),
    }


def edge_metadata_to_json(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return edge metadata in a JSONB-safe shape, excluding ``edge_type``."""
    converted: dict[str, Any] = {}
    for metadata_key, metadata_value in metadata.items():
        if metadata_key == _COL_EDGE_TYPE:
            continue
        converted[metadata_key] = _json_safe(metadata_value)
    return converted


def _json_safe(raw_value: Any) -> Any:
    if isinstance(raw_value, UUID):
        return str(raw_value)
    if isinstance(raw_value, Enum):
        return raw_value.value
    if isinstance(raw_value, list | tuple):
        return [_json_safe(metadata_entry) for metadata_entry in raw_value]
    if isinstance(raw_value, dict):
        converted: dict[str, Any] = {}
        for metadata_key, metadata_value in raw_value.items():
            converted[str(metadata_key)] = _json_safe(metadata_value)
        return converted
    return raw_value
