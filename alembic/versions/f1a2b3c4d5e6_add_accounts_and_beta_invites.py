"""add accounts and beta invites

Revision ID: f1a2b3c4d5e6
Revises: a2b3c4d5e6f7
Create Date: 2026-05-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACCOUNTS = "accounts"
_BETA_INVITES = "beta_invites"


def upgrade() -> None:
    op.create_table(
        _ACCOUNTS,
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("supabase_user_id", sa.String(length=128), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="friend_beta"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("supabase_user_id", name="uq_accounts_supabase_user_id"),
    )
    op.create_table(
        _BETA_INVITES,
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="invited"),
        sa.Column("invited_by", UUID(as_uuid=True), nullable=True),
        sa.Column("invited_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("accepted_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_beta_invites_email"),
    )


def downgrade() -> None:
    op.drop_table(_BETA_INVITES)
    op.drop_table(_ACCOUNTS)
