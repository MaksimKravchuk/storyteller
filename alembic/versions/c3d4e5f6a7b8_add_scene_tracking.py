"""add scene_number and scene_conversation_log to game_states

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-26 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_states",
        sa.Column("scene_number", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "game_states",
        sa.Column("scene_conversation_log", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("game_states", "scene_conversation_log")
    op.drop_column("game_states", "scene_number")
