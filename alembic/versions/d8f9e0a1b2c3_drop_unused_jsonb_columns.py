"""drop unused JSONB columns: settings.raw_sources and players.interaction_history

Revision ID: d8f9e0a1b2c3
Revises: a0c1e2f3b4d5
Create Date: 2026-04-30 00:00:00.000000

Neither column is read in production. ``raw_sources`` is written once in
``cast/data_miner.py`` but never consumed; ``interaction_history`` has zero
writers in ``cast/`` or ``engine/``. Removing both alongside the model fields.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "d8f9e0a1b2c3"
down_revision = "a0c1e2f3b4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("settings", "raw_sources")
    op.drop_column("players", "interaction_history")


def downgrade() -> None:
    op.add_column(
        "players",
        sa.Column("interaction_history", JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "settings",
        sa.Column("raw_sources", JSONB, nullable=False, server_default="[]"),
    )
