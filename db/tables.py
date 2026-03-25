"""SQLAlchemy table definitions (Core style, not ORM-mapped)."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

metadata = MetaData()

sessions = Table(
    "sessions",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()),
    Column("telegram_chat_id", Integer, unique=True, nullable=False),
    Column("state", String(32), nullable=False, server_default="idle"),
    Column("language", String(32), nullable=False, server_default="English"),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
)

game_states = Table(
    "game_states",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()),
    Column("session_id", UUID(as_uuid=False), ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, nullable=False),
    Column("turn_count", Integer, nullable=False, server_default="0"),
    Column("game_clock", Float, nullable=False, server_default="0.0"),
    Column("game_time", String(16), nullable=False, server_default="morning"),
    Column("conversation_log", JSONB, nullable=False, server_default="[]"),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
)

settings = Table(
    "settings",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()),
    Column("game_state_id", UUID(as_uuid=False), ForeignKey("game_states.id", ondelete="CASCADE"), unique=True, nullable=False),
    Column("name", Text, nullable=False),
    Column("time_period", Text, nullable=False),
    Column("region", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("key_persons", JSONB, nullable=False, server_default="[]"),
    Column("key_events", JSONB, nullable=False, server_default="[]"),
    Column("locations_data", JSONB, nullable=False, server_default="[]"),
    Column("traditions", JSONB, nullable=False, server_default="[]"),
    Column("technologies", JSONB, nullable=False, server_default="[]"),
    Column("social_structure", Text, nullable=False, server_default=""),
    Column("raw_sources", JSONB, nullable=False, server_default="[]"),
)

players = Table(
    "players",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()),
    Column("game_state_id", UUID(as_uuid=False), ForeignKey("game_states.id", ondelete="CASCADE"), unique=True, nullable=False),
    Column("name", String(128), nullable=False, server_default="Player"),
    Column("location_id", Text, nullable=True),
    Column("inventory", JSONB, nullable=False, server_default="[]"),
    Column("appearance", Text, nullable=False, server_default=""),
    Column("interaction_history", JSONB, nullable=False, server_default="[]"),
)

locations = Table(
    "locations",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("game_state_id", UUID(as_uuid=False), ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("parent_location_id", Text, nullable=True),
    Column("location_type", String(32), nullable=False, server_default="generic"),
    Column("tags", JSONB, nullable=False, server_default="[]"),
    Column("connected_locations", JSONB, nullable=False, server_default="[]"),
    Column("npcs_present", JSONB, nullable=False, server_default="[]"),
    Column("points_of_interest", JSONB, nullable=False, server_default="[]"),
    Index("idx_locations_game_state", "game_state_id"),
)

npcs = Table(
    "npcs",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("game_state_id", UUID(as_uuid=False), ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
    Column("name", Text, nullable=False),
    Column("biography", Text, nullable=False, server_default=""),
    Column("appearance", Text, nullable=False, server_default=""),
    Column("occupation", Text, nullable=False, server_default=""),
    Column("personality_traits", JSONB, nullable=False, server_default="[]"),
    Column("speech_style", Text, nullable=False, server_default=""),
    Column("knowledge_scope", String(16), nullable=False, server_default="local"),
    Column("attributes", JSONB, nullable=False, server_default="{}"),
    Column("inventory", JSONB, nullable=False, server_default="[]"),
    Column("location_id", Text, nullable=True),
    Column("relationships", JSONB, nullable=False, server_default="{}"),
    Column("conversation_history", JSONB, nullable=False, server_default="[]"),
    Column("current_mood", String(32), nullable=False, server_default="neutral"),
    Index("idx_npcs_game_state", "game_state_id"),
)

scenes = Table(
    "scenes",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("game_state_id", UUID(as_uuid=False), ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
    Column("is_current", Boolean, nullable=False, server_default="false"),
    Column("location_id", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("npcs_present", JSONB, nullable=False, server_default="[]"),
    Column("points_of_interest", JSONB, nullable=False, server_default="[]"),
    Column("ambient_description", Text, nullable=False, server_default=""),
    Column("time_of_day", String(16), nullable=False, server_default="day"),
    Column("narrated_text", Text, nullable=False, server_default=""),
    Index("idx_scenes_game_state", "game_state_id"),
)

knowledge_nodes = Table(
    "knowledge_nodes",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("game_state_id", UUID(as_uuid=False), ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
    Column("content", Text, nullable=False),
    Column("scope", String(16), nullable=False, server_default="local"),
    Column("source", String(16), nullable=False, server_default="fact"),
    Column("required_education", Integer, nullable=False, server_default="0"),
    Column("required_social_status", Integer, nullable=False, server_default="0"),
    Column("tags", JSONB, nullable=False, server_default="[]"),
    Column("location_id", Text, nullable=True),
    Column("timestamp", Float, nullable=True),
    Column("confidence", Float, nullable=False, server_default="1.0"),
    Index("idx_kn_game_state", "game_state_id"),
    Index("idx_kn_scope", "game_state_id", "scope"),
    Index("idx_kn_tags", "tags", postgresql_using="gin"),
)

knowledge_edges = Table(
    "knowledge_edges",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("game_state_id", UUID(as_uuid=False), ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
    Column("from_node_id", UUID(as_uuid=False), nullable=False),
    Column("to_node_id", UUID(as_uuid=False), nullable=False),
    Column("edge_type", String(32), nullable=False, server_default="related_to"),
    Column("metadata_", JSONB, nullable=False, server_default="{}"),
    Index("idx_ke_from", "game_state_id", "from_node_id"),
    Index("idx_ke_to", "game_state_id", "to_node_id"),
)

game_events = Table(
    "game_events",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("game_state_id", UUID(as_uuid=False), ForeignKey("game_states.id", ondelete="CASCADE"), nullable=False),
    Column("name", Text, nullable=False),
    Column("scheduled_at", Float, nullable=False),
    Column("duration", Float, nullable=False),
    Column("completes_at", Float, nullable=False),
    Column("status", String(16), nullable=False, server_default="pending"),
    Column("owner_id", Text, nullable=True),
    Column("location_id", Text, nullable=True),
    Column("scope", String(16), nullable=False, server_default="local"),
    Column("effects", JSONB, nullable=False, server_default="[]"),
    Column("follow_up_events", JSONB, nullable=False, server_default="[]"),
    Column("on_complete_description", Text, nullable=False, server_default=""),
    Index("idx_events_game_state", "game_state_id"),
)
