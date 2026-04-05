"""add round_number to game_states

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-05 08:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    col = sa.Column("round_number", sa.Integer(), nullable=False, server_default="0")
    op.add_column("game_states", col)


def downgrade() -> None:
    op.drop_column("game_states", "round_number")
