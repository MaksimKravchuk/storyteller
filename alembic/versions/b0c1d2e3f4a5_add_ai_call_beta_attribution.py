"""add beta attribution to AI call logs

Revision ID: b0c1d2e3f4a5
Revises: 9a0b1c2d3e4f
Create Date: 2026-05-24 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "9a0b1c2d3e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_call_logs", sa.Column("user_id", sa.Text(), nullable=True))
    op.add_column(
        "ai_call_logs",
        sa.Column("game_state_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "idx_ai_calls_user_created",
        "ai_call_logs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_ai_calls_model_created",
        "ai_call_logs",
        ["model", "created_at"],
    )
    op.create_index(
        "idx_ai_calls_game_state",
        "ai_call_logs",
        ["game_state_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_ai_calls_game_state", table_name="ai_call_logs")
    op.drop_index("idx_ai_calls_model_created", table_name="ai_call_logs")
    op.drop_index("idx_ai_calls_user_created", table_name="ai_call_logs")
    op.drop_column("ai_call_logs", "game_state_id")
    op.drop_column("ai_call_logs", "user_id")
