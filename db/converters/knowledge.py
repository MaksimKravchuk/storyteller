"""KnowledgeNode ↔ DB row converters."""

from __future__ import annotations

from db.converters._columns import COL_GAME_STATE_ID, COL_ID, COL_LOCATION_ID, COL_SCOPE, COL_TAGS
from db.converters._uuid_text import uuid_to_text
from knowledge.node import CanonSource, KnowledgeNode, KnowledgeScope, KnowledgeSource

_COL_CANON = "canon"
_DEFAULT_CANON = CanonSource.HISTORICAL.value


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
    )
