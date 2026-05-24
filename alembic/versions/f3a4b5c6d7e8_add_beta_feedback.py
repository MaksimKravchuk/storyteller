"""Add beta feedback table.

Revision ID: f3a4b5c6d7e8
Revises: b0c1d2e3f4a5
Create Date: 2026-05-24 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3a4b5c6d7e8"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create beta feedback capture table."""
    op.create_table(
        "beta_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_email", sa.Text(), nullable=True),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["game_states.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_beta_feedback_created", "beta_feedback", ["created_at"])
    op.create_index("idx_beta_feedback_game", "beta_feedback", ["game_id"])
    op.create_index("idx_beta_feedback_user_created", "beta_feedback", ["user_id", "created_at"])


def downgrade() -> None:
    """Drop beta feedback capture table."""
    op.drop_index("idx_beta_feedback_user_created", table_name="beta_feedback")
    op.drop_index("idx_beta_feedback_game", table_name="beta_feedback")
    op.drop_index("idx_beta_feedback_created", table_name="beta_feedback")
    op.drop_table("beta_feedback")
