"""add story_arc to game_states

Revision ID: d3673f69b8d5
Revises: c9d0e1f2a3b4
Create Date: 2026-04-12 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "d3673f69b8d5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_states",
        sa.Column("story_arc", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("game_states", "story_arc")
