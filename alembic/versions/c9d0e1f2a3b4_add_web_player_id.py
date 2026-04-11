"""add web_player_id to sessions and relax telegram_chat_id

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-04-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "sessions"
_UNIQUE_NAME = "uq_sessions_web_player_id"


def upgrade() -> None:
    # Sessions created by the web UI are keyed by web_player_id instead of
    # telegram_chat_id, so telegram_chat_id must become nullable. A UNIQUE
    # index on a nullable column still allows multiple NULLs in Postgres.
    op.alter_column(_TABLE, "telegram_chat_id", nullable=True)
    op.add_column(
        _TABLE,
        sa.Column("web_player_id", UUID(as_uuid=False), nullable=True),
    )
    op.create_unique_constraint(_UNIQUE_NAME, _TABLE, ["web_player_id"])


def downgrade() -> None:
    op.drop_constraint(_UNIQUE_NAME, _TABLE, type_="unique")
    op.drop_column(_TABLE, "web_player_id")
    op.alter_column(_TABLE, "telegram_chat_id", nullable=False)
