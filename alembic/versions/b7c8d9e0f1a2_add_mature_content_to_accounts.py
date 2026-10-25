"""Add the account-level 18+ (mature content) switch.

Revision ID: b7c8d9e0f1a2
Revises: 5c3d9d120dd6
Create Date: 2026-10-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "5c3d9d120dd6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("mature_content", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("accounts", "mature_content")
