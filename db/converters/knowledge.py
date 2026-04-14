"""KnowledgeNode ↔ DB row converters."""

from __future__ import annotations

from db.converters._columns import COL_GAME_STATE_ID, COL_ID, COL_LOCATION_ID, COL_SCOPE, COL_TAGS
from knowledge.node import KnowledgeCanon, KnowledgeNode, KnowledgeScope, KnowledgeSource


def knowledge_node_to_row(node: KnowledgeNode, game_state_id: str) -> dict:
    return {
        COL_ID: node.uuid,
        COL_GAME_STATE_ID: game_state_id,
        "content": node.text,
        COL_SCOPE: node.scope.value,
        "source": node.source.value,
        "canon": node.canon.value,
        "required_education": node.required_education,
        "required_social_status": node.required_social_status,
        COL_TAGS: node.tags,
        COL_LOCATION_ID: node.location_id,
        "timestamp": node.timestamp,
        "confidence": node.confidence,
    }


def row_to_knowledge_node(row) -> KnowledgeNode:
    return KnowledgeNode(
        uuid=row[COL_ID],
        text=row["content"],
        scope=KnowledgeScope(row[COL_SCOPE]),
        source=KnowledgeSource(row["source"]),
        canon=KnowledgeCanon(row["canon"]),
        required_education=row["required_education"],
        required_social_status=row["required_social_status"],
        tags=row[COL_TAGS],
        location_id=row[COL_LOCATION_ID],
        timestamp=row["timestamp"],
        confidence=row["confidence"],
    )
