"""Promote NPC relationships from dict[str,str] to list[Relationship].

Revision ID: e1f2a3b4c5d6
Revises: d8f9e0a1b2c3
Create Date: 2026-05-02
"""

from __future__ import annotations

import json
import re
import uuid

import sqlalchemy as sa
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d8f9e0a1b2c3"
branch_labels = None
depends_on = None

_HOSTILITY_KEYWORDS = frozenset(
    ("kill", "murder", "murderous", "harm", "wound", "enemy", "rival", "foe", "vendetta", "vengeance", "hostile"),
)
_TOKEN_RE = r"(?:^|[^a-zA-Z])(?:{0})(?:[^a-zA-Z]|$)"
_HOSTILITY_RE = re.compile(_TOKEN_RE.format("|".join(_HOSTILITY_KEYWORDS)), re.IGNORECASE)

# `CAST(:rels AS jsonb)` rather than `:rels::jsonb`: SQLAlchemy's text() parser
# treats `::` as part of an escape and silently mis-binds the named parameter.
UPDATE_NPC_RELATIONSHIPS_SQL = "UPDATE npcs SET relationships = CAST(:rels AS jsonb) WHERE id = :id"


def _infer_kind(label: str) -> str:
    if _HOSTILITY_RE.search(label):
        return "enemy"
    return "neutral"


def _upcast(raw: dict) -> list[dict]:
    result = []
    for target_uuid_str, label in raw.items():
        safe_label = label or ""
        kind = _infer_kind(safe_label)
        result.append(
            {
                "uuid": str(uuid.uuid4()),
                "target_uuid": target_uuid_str,
                "kind": kind,
                "intensity": -3 if kind == "enemy" else 0,
                "note": safe_label,
                "established_turn": None,
                "source_thread_uuid": None,
            }
        )
    return result


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, relationships FROM npcs")).fetchall()
    for row_id, rels in rows:
        if not isinstance(rels, dict):
            continue
        new_rels = _upcast(rels)
        conn.execute(
            sa.text(UPDATE_NPC_RELATIONSHIPS_SQL),
            {"rels": json.dumps(new_rels), "id": row_id},
        )


def downgrade() -> None:
    pass
