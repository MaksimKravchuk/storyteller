"""add turn_events

Revision ID: b4c5d6e7f8a9
Revises: b9c0d1e2f3a4
Create Date: 2026-04-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID


# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "turn_events",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.func.gen_random_uuid(),
            primary_key=True,
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=False),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_number", sa.Integer, nullable=True),
        sa.Column("scene_number", sa.Integer, nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=True),
        sa.Column("npc_id", UUID(as_uuid=False), nullable=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("sequence", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_turn_events_session_turn", "turn_events", ["session_id", "turn_number"])
    op.create_index("idx_turn_events_session_npc", "turn_events", ["session_id", "npc_id"])
    op.create_index("idx_turn_events_type", "turn_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_turn_events_type", table_name="turn_events")
    op.drop_index("idx_turn_events_session_npc", table_name="turn_events")
    op.drop_index("idx_turn_events_session_turn", table_name="turn_events")
    op.drop_table("turn_events")
