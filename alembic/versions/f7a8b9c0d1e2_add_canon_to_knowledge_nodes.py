"""add canon column to knowledge_nodes

Revision ID: f7a8b9c0d1e2
Revises: e3a1b2c4d5f6
Create Date: 2026-04-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e3a1b2c4d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    col = sa.Column("canon", sa.String(16), nullable=False, server_default="historical")
    op.add_column("knowledge_nodes", col)


def downgrade() -> None:
    op.drop_column("knowledge_nodes", "canon")
