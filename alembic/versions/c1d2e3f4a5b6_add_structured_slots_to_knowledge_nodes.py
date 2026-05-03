"""add structured memory slots to knowledge_nodes

Revision ID: c1d2e3f4a5b6
Revises: c2d3e4f5a6b7
Create Date: 2026-05-03 10:00:00.000000

Adds structured ``subject``/``object``/``action``/``outcome`` slots
alongside the existing free-text ``content``. All four are nullable so
historical Wikipedia facts and other sites without a clear actor leave
them as ``NULL``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_nodes", sa.Column("subject", sa.Text(), nullable=True))
    op.add_column("knowledge_nodes", sa.Column("object", sa.Text(), nullable=True))
    op.add_column("knowledge_nodes", sa.Column("action", sa.Text(), nullable=True))
    op.add_column("knowledge_nodes", sa.Column("outcome", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_nodes", "outcome")
    op.drop_column("knowledge_nodes", "action")
    op.drop_column("knowledge_nodes", "object")
    op.drop_column("knowledge_nodes", "subject")
