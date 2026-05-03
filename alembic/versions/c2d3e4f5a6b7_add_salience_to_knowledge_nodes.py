"""add salience to knowledge_nodes

Revision ID: c2d3e4f5a6b7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-03 12:00:00.000000

Per-memory importance score so ``KnowledgeQueryEngine.get_memories_held_by``
can rank pivotal events (combat, deaths) above routine chatter rather
than relying on pure recency. Existing rows backfill to 0.5 — the
neutral midpoint — which keeps pre-existing memories ordered by
recency under the salience+recency blend.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_nodes",
        sa.Column(
            "salience",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_nodes", "salience")
