"""add known_npcs, player_event_log, learned_facts to players

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-04-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("known_npcs", JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "players",
        sa.Column("player_event_log", JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "players",
        sa.Column("learned_facts", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("players", "learned_facts")
    op.drop_column("players", "player_event_log")
    op.drop_column("players", "known_npcs")
