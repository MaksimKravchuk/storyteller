"""initial schema

Revision ID: d9140b2bcae6
Revises:
Create Date: 2026-03-25 09:49:39.062208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID


# revision identifiers, used by Alembic.
revision: str = 'd9140b2bcae6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("telegram_chat_id", sa.Integer, unique=True, nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="idle"),
        sa.Column("language", sa.String(32), nullable=False, server_default="English"),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "game_states",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("session_id", UUID(as_uuid=False), sa.ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("turn_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("game_clock", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("game_time", sa.String(16), nullable=False, server_default="morning"),
        sa.Column("conversation_log", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "settings",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("game_state_id", UUID(as_uuid=False), sa.ForeignKey("game_states.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("time_period", sa.Text, nullable=False),
        sa.Column("region", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("key_persons", JSONB, nullable=False, server_default="[]"),
        sa.Column("key_events", JSONB, nullable=False, server_default="[]"),
        sa.Column("locations_data", JSONB, nullable=False, server_default="[]"),
        sa.Column("traditions", JSONB, nullable=False, server_default="[]"),
        sa.Column("technologies", JSONB, nullable=False, server_default="[]"),
        sa.Column("social_structure", sa.Text, nullable=False, server_default=""),
        sa.Column("raw_sources", JSONB, nullable=False, server_default="[]"),
    )

    op.create_table(
        "players",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("game_state_id", UUID(as_uuid=False), sa.ForeignKey("game_states.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False, server_default="Player"),
        sa.Column("location_id", sa.Text, nullable=True),
        sa.Column("inventory", JSONB, nullable=False, server_default="[]"),
        sa.Column("appearance", sa.Text, nullable=False, server_default=""),
        sa.Column("interaction_history", JSONB, nullable=False, server_default="[]"),
    )

    op.create_table(
        "locations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("game_state_id", UUID(as_uuid=False), sa.ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("parent_location_id", sa.Text, nullable=True),
        sa.Column("location_type", sa.String(32), nullable=False, server_default="generic"),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("connected_locations", JSONB, nullable=False, server_default="[]"),
        sa.Column("npcs_present", JSONB, nullable=False, server_default="[]"),
        sa.Column("points_of_interest", JSONB, nullable=False, server_default="[]"),
    )
    op.create_index("idx_locations_game_state", "locations", ["game_state_id"])

    op.create_table(
        "npcs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("game_state_id", UUID(as_uuid=False), sa.ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("biography", sa.Text, nullable=False, server_default=""),
        sa.Column("appearance", sa.Text, nullable=False, server_default=""),
        sa.Column("occupation", sa.Text, nullable=False, server_default=""),
        sa.Column("personality_traits", JSONB, nullable=False, server_default="[]"),
        sa.Column("speech_style", sa.Text, nullable=False, server_default=""),
        sa.Column("knowledge_scope", sa.String(16), nullable=False, server_default="local"),
        sa.Column("attributes", JSONB, nullable=False, server_default="{}"),
        sa.Column("inventory", JSONB, nullable=False, server_default="[]"),
        sa.Column("location_id", sa.Text, nullable=True),
        sa.Column("relationships", JSONB, nullable=False, server_default="{}"),
        sa.Column("conversation_history", JSONB, nullable=False, server_default="[]"),
        sa.Column("current_mood", sa.String(32), nullable=False, server_default="neutral"),
    )
    op.create_index("idx_npcs_game_state", "npcs", ["game_state_id"])

    op.create_table(
        "scenes",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("game_state_id", UUID(as_uuid=False), sa.ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("location_id", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("npcs_present", JSONB, nullable=False, server_default="[]"),
        sa.Column("points_of_interest", JSONB, nullable=False, server_default="[]"),
        sa.Column("ambient_description", sa.Text, nullable=False, server_default=""),
        sa.Column("time_of_day", sa.String(16), nullable=False, server_default="day"),
        sa.Column("narrated_text", sa.Text, nullable=False, server_default=""),
    )
    op.create_index("idx_scenes_game_state", "scenes", ["game_state_id"])

    op.create_table(
        "knowledge_nodes",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("game_state_id", UUID(as_uuid=False), sa.ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("scope", sa.String(16), nullable=False, server_default="local"),
        sa.Column("source", sa.String(16), nullable=False, server_default="fact"),
        sa.Column("required_education", sa.Integer, nullable=False, server_default="0"),
        sa.Column("required_social_status", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("location_id", sa.Text, nullable=True),
        sa.Column("timestamp", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
    )
    op.create_index("idx_kn_game_state", "knowledge_nodes", ["game_state_id"])
    op.create_index("idx_kn_scope", "knowledge_nodes", ["game_state_id", "scope"])
    op.create_index("idx_kn_tags", "knowledge_nodes", ["tags"], postgresql_using="gin")

    op.create_table(
        "knowledge_edges",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("game_state_id", UUID(as_uuid=False), sa.ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_node_id", UUID(as_uuid=False), nullable=False),
        sa.Column("to_node_id", UUID(as_uuid=False), nullable=False),
        sa.Column("edge_type", sa.String(32), nullable=False, server_default="related_to"),
        sa.Column("metadata_", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("idx_ke_from", "knowledge_edges", ["game_state_id", "from_node_id"])
    op.create_index("idx_ke_to", "knowledge_edges", ["game_state_id", "to_node_id"])

    op.create_table(
        "game_events",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("game_state_id", UUID(as_uuid=False), sa.ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("scheduled_at", sa.Float, nullable=False),
        sa.Column("duration", sa.Float, nullable=False),
        sa.Column("completes_at", sa.Float, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("owner_id", sa.Text, nullable=True),
        sa.Column("location_id", sa.Text, nullable=True),
        sa.Column("scope", sa.String(16), nullable=False, server_default="local"),
        sa.Column("effects", JSONB, nullable=False, server_default="[]"),
        sa.Column("follow_up_events", JSONB, nullable=False, server_default="[]"),
        sa.Column("on_complete_description", sa.Text, nullable=False, server_default=""),
    )
    op.create_index("idx_events_game_state", "game_events", ["game_state_id"])


def downgrade() -> None:
    op.drop_table("game_events")
    op.drop_table("knowledge_edges")
    op.drop_table("knowledge_nodes")
    op.drop_table("scenes")
    op.drop_table("npcs")
    op.drop_table("locations")
    op.drop_table("players")
    op.drop_table("settings")
    op.drop_table("game_states")
    op.drop_table("sessions")
