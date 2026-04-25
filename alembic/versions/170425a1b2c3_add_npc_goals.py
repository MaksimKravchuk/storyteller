"""add life_goal and tactical_goal to npcs

Revision ID: 170425a1b2c3
Revises: 06789c3ff6e2
Create Date: 2026-04-25 12:00:00.000000

NPCs gained an autonomous goal system (life-tier and tactical-tier ``Goal``
pydantic models). These columns persist them across ``persist_engine`` /
``restore_engine`` cycles. Both are nullable JSONB; ``NULL`` means "no
goal set" rather than an empty object.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "170425a1b2c3"
down_revision: Union[str, None] = "06789c3ff6e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("npcs", sa.Column("life_goal", JSONB, nullable=True))
    op.add_column("npcs", sa.Column("tactical_goal", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("npcs", "tactical_goal")
    op.drop_column("npcs", "life_goal")
