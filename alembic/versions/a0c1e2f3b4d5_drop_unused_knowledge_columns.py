"""drop required_social_status and confidence from knowledge_nodes

Revision ID: a0c1e2f3b4d5
Revises: c4d5e6f7a8b9
Create Date: 2026-04-29 18:00:00.000000

Both fields were persisted but never used to gate behavior:
required_social_status was always 0, confidence was always 1.0.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a0c1e2f3b4d5"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("knowledge_nodes", "required_social_status")
    op.drop_column("knowledge_nodes", "confidence")


def downgrade() -> None:
    op.add_column(
        "knowledge_nodes",
        sa.Column(
            "confidence",
            sa.Float,
            nullable=False,
            server_default="1.0",
        ),
    )
    op.add_column(
        "knowledge_nodes",
        sa.Column(
            "required_social_status",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
