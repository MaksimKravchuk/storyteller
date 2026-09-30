"""Add story posters (library playbills and on-demand illustrations).

Revision ID: a9b0c1d2e3f4
Revises: e8f9a0b1c2d3
Create Date: 2026-09-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a9b0c1d2e3f4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None

_TABLE = "story_posters"


def upgrade() -> None:
    """Create the one-row-per-session story poster table."""
    op.create_table(
        _TABLE,
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbill", postgresql.JSONB(), nullable=False),
        sa.Column("image", postgresql.BYTEA(), nullable=True),
        sa.Column("image_mime", sa.String(length=32), nullable=True),
        sa.Column("image_created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )


def downgrade() -> None:
    """Drop the story poster table."""
    op.drop_table(_TABLE)
