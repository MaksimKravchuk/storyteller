"""drop telegram session identity

Revision ID: a1b2c3d4e5f7
Revises: f3a4b5c6d7e8
Create Date: 2026-05-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "sessions"
_INDEX = "idx_sessions_telegram_chat_id"
_COLUMN = "telegram_chat_id"


def upgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_column(_TABLE, _COLUMN)


def downgrade() -> None:
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.Integer(), nullable=True))
    op.create_index(_INDEX, _TABLE, [_COLUMN])
