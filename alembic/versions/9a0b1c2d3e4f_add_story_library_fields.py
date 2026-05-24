"""add story library fields to sessions

Revision ID: 9a0b1c2d3e4f
Revises: f1a2b3c4d5e6
Create Date: 2026-05-24 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9a0b1c2d3e4f"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("title", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("archived_at", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.create_index("idx_sessions_web_player_active", "sessions", ["web_player_id", "archived_at"])


def downgrade() -> None:
    op.drop_index("idx_sessions_web_player_active", table_name="sessions")
    op.drop_column("sessions", "archived_at")
    op.drop_column("sessions", "title")
