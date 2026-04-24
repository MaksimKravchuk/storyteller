"""add admin_settings table

Revision ID: 06789c3ff6e2
Revises: f7b8c9d0e1a2
Create Date: 2026-04-24 12:00:00.000000

Key-value store for operator-mutable runtime settings (currently: per-role
model overrides). Empty table preserves existing env-var behavior.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "06789c3ff6e2"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("admin_settings")
