"""add physical_status to players

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-05 08:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

_STATUS_MAX_LENGTH = 128

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("physical_status", sa.String(_STATUS_MAX_LENGTH), nullable=False, server_default="healthy"),
    )


def downgrade() -> None:
    op.drop_column("players", "physical_status")
