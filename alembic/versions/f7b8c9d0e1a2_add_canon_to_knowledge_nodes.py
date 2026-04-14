"""add canon to knowledge_nodes

Revision ID: f7b8c9d0e1a2
Revises: e3a1b2c4d5f6
Create Date: 2026-04-14 10:00:00.000000

KER-7: distinguish DataMiner-researched "historical" knowledge from
player-caused "session" knowledge so a future Dramaturge / conflict
detector can avoid flagging legitimate in-session facts as contradicting
Wikipedia.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

_CANON_MAX_LENGTH = 16

# revision identifiers, used by Alembic.
revision: str = "f7b8c9d0e1a2"
down_revision: Union[str, None] = "e3a1b2c4d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_nodes",
        sa.Column(
            "canon",
            sa.String(_CANON_MAX_LENGTH),
            nullable=False,
            server_default="historical",
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_nodes", "canon")
