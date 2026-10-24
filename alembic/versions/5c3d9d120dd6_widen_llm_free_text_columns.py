"""Widen LLM-written free-text columns to TEXT.

NPC mood / status / knowledge scope, player status and scene time-of-day
come straight from LLM output with no length cap; a long value made the
whole ``save_game_state`` fail with ``value too long``. VARCHAR → TEXT is a
metadata-only change in Postgres (no table rewrite).

Revision ID: 5c3d9d120dd6
Revises: a9b0c1d2e3f4
Create Date: 2026-10-24 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5c3d9d120dd6"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None

# (table, column, previous VARCHAR length)
_COLUMNS = (
    ("npcs", "current_mood", 32),
    ("npcs", "physical_status", 128),
    ("npcs", "knowledge_scope", 16),
    ("players", "physical_status", 128),
    ("scenes", "time_of_day", 16),
)


def upgrade() -> None:
    """Change each LLM-written column to unbounded TEXT."""
    for table, column, length in _COLUMNS:
        op.alter_column(table, column, type_=sa.Text(), existing_type=sa.String(length), existing_nullable=False)


def downgrade() -> None:
    """Restore the VARCHAR limits, truncating values that no longer fit."""
    for table, column, length in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.String(length),
            existing_type=sa.Text(),
            existing_nullable=False,
            postgresql_using="left({0}, {1})".format(column, length),
        )
