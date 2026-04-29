"""drop follow_up_events column from game_events

Revision ID: a1b2c3d4e5f6
Revises: f7b8c9d0e1a2
Create Date: 2026-04-29 00:00:00.000000

No production caller ever populated follow_up_events; removing the dead
column and the corresponding domain-model field.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a1b2c3d4e5f6"
down_revision = "f7b8c9d0e1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("game_events", "follow_up_events")


def downgrade() -> None:
    op.add_column(
        "game_events",
        sa.Column(
            "follow_up_events",
            JSONB,
            nullable=False,
            server_default="[]",
        ),
    )
