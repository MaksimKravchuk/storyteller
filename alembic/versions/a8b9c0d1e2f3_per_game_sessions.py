"""drop unique constraints on player identifiers so each game gets its own session

Revision ID: a8b9c0d1e2f3
Revises: f7b8c9d0e1a2
Create Date: 2026-04-15 10:00:00.000000

Each started game now creates a fresh ``sessions`` row. The unique constraints
on ``telegram_chat_id`` / ``web_player_id`` used to enforce one-session-per-player,
which caused ``ai_call_logs`` from multiple games to pile onto the same session.
Replace the unique indexes with non-unique B-tree indexes so "find latest
session for player" lookups stay fast.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "f7b8c9d0e1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "sessions"
_UNIQUE_WEB = "uq_sessions_web_player_id"
_UNIQUE_TELEGRAM = "sessions_telegram_chat_id_key"
_INDEX_WEB = "idx_sessions_web_player_id"
_INDEX_TELEGRAM = "idx_sessions_telegram_chat_id"


def upgrade() -> None:
    op.drop_constraint(_UNIQUE_WEB, _TABLE, type_="unique")
    op.drop_constraint(_UNIQUE_TELEGRAM, _TABLE, type_="unique")
    op.create_index(_INDEX_TELEGRAM, _TABLE, ["telegram_chat_id"])
    op.create_index(_INDEX_WEB, _TABLE, ["web_player_id"])


def downgrade() -> None:
    op.drop_index(_INDEX_WEB, table_name=_TABLE)
    op.drop_index(_INDEX_TELEGRAM, table_name=_TABLE)
    op.create_unique_constraint(_UNIQUE_TELEGRAM, _TABLE, ["telegram_chat_id"])
    op.create_unique_constraint(_UNIQUE_WEB, _TABLE, ["web_player_id"])
