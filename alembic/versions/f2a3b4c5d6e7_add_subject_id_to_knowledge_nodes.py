"""add subject_id to knowledge_nodes

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-03

The column is nullable Text because the value is polymorphic — a player
UUID or an NPC UUID — so a foreign key would forbid valid rows.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_nodes",
        sa.Column("subject_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_nodes", "subject_id")
