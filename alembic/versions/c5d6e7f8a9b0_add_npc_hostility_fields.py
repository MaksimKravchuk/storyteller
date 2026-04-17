"""add hostility_level and recent_hostile_actions to npcs

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-04-17 01:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "npcs",
        sa.Column("hostility_level", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "npcs",
        sa.Column("recent_hostile_actions", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("npcs", "recent_hostile_actions")
    op.drop_column("npcs", "hostility_level")
