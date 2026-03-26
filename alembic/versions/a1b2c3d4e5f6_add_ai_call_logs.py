"""add ai_call_logs

Revision ID: a1b2c3d4e5f6
Revises: d9140b2bcae6
Create Date: 2026-03-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d9140b2bcae6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_call_logs",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.func.gen_random_uuid(), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=False), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_number", sa.Integer, nullable=True),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("messages", JSONB, nullable=False),
        sa.Column("response_content", sa.Text, nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ai_calls_session", "ai_call_logs", ["session_id"])
    op.create_index("idx_ai_calls_session_turn", "ai_call_logs", ["session_id", "turn_number"])
    op.create_index("idx_ai_calls_created", "ai_call_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_ai_calls_created", table_name="ai_call_logs")
    op.drop_index("idx_ai_calls_session_turn", table_name="ai_call_logs")
    op.drop_index("idx_ai_calls_session", table_name="ai_call_logs")
    op.drop_table("ai_call_logs")
