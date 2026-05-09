"""add scene_action_log to game_states

Revision ID: a2b3c4d5e6f7
Revises: f2a3b4c5d6e7
Create Date: 2026-05-09 12:00:00.000000

Per-scene action log used as NPC short-term memory. Populated each
turn with player actions, NPC actions/dialogue, and witnessed events;
consolidated into long-term memory and cleared on scene swap.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_states",
        sa.Column(
            "scene_action_log",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("game_states", "scene_action_log")
