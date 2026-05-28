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
)
from sqlalchemy import (
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

metadata = MetaData()

# Reusable column type: native Postgres UUID round-tripped as Python ``uuid.UUID``.
_UUID_STR = UUID(as_uuid=True)

# Column name constants
_COL_ID = "id"
_COL_GAME_STATE_ID = "game_state_id"
_COL_SESSION_ID = "session_id"
_COL_NAME = "name"
_COL_LOCATION_ID = "location_id"
_COL_CREATED_AT = "created_at"
_COL_TURN_NUMBER = "turn_number"
_FK_GAME_STATES_ID = "game_states.id"
_FK_SESSIONS_ID = "sessions.id"
_ON_DELETE_CASCADE = "CASCADE"


def _fk_game_state() -> ForeignKey:
    """Create a ForeignKey to game_states.id with CASCADE delete."""
    return ForeignKey(_FK_GAME_STATES_ID, ondelete=_ON_DELETE_CASCADE)


# Server-default literals
_DEFAULT_ZERO = "0"
_DEFAULT_JSON_ARRAY = "[]"
_DEFAULT_JSON_OBJECT = "{}"

# String column lengths
_LEN_TINY = 16
_LEN_SHORT = 32
_LEN_MEDIUM = 64
_LEN_LONG = 128
_COL_USER_ID = "user_id"

# Reusable String type instances — avoid WPS204 "overused expression"
_TINY_STR = String(_LEN_TINY)
_SHORT_STR = String(_LEN_SHORT)
_SHORT_TEXT = String(_LEN_SHORT)
_TZ_TS = TIMESTAMP(timezone=True)


def _uuid_pk_column() -> Column:
    """Create a UUID primary key column with the project default."""
    return Column(_COL_ID, _UUID_STR, primary_key=True, server_default=func.gen_random_uuid())


accounts = Table(
    "accounts",
    metadata,
    _uuid_pk_column(),
    Column("supabase_user_id", String(_LEN_LONG), nullable=False),
    Column("email", Text, nullable=False),
    Column("plan", _SHORT_STR, nullable=False, server_default="friend_beta"),
    Column("is_admin", Boolean, nullable=False, server_default="false"),
    Column(_COL_CREATED_AT, _TZ_TS, nullable=False, server_default=func.now()),
    Column("updated_at", _TZ_TS, nullable=False, server_default=func.now()),
    UniqueConstraint("supabase_user_id", name="uq_accounts_supabase_user_id"),
)

beta_invites = Table(
    "beta_invites",
    metadata,
    _uuid_pk_column(),
    Column("email", Text, nullable=False),
    Column("status", _SHORT_STR, nullable=False, server_default="invited"),
    Column("invited_by", _UUID_STR, nullable=True),
    Column("invited_at", _TZ_TS, nullable=False, server_default=func.now()),
    Column("accepted_at", _TZ_TS, nullable=True),
    Column(_COL_CREATED_AT, _TZ_TS, nullable=False, server_default=func.now()),
    UniqueConstraint("email", name="uq_beta_invites_email"),
)

sessions = Table(
    "sessions",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True, server_default=func.gen_random_uuid()),
    Column("web_player_id", _UUID_STR, nullable=True),
    Column("state", _SHORT_TEXT, nullable=False, server_default="idle"),
    Column("language", _SHORT_TEXT, nullable=False, server_default="English"),
    Column("title", Text, nullable=True),
    Column("archived_at", _TZ_TS, nullable=True),
    Column(_COL_CREATED_AT, TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Index("idx_sessions_web_player_id", "web_player_id"),
)

game_states = Table(
    "game_states",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True, server_default=func.gen_random_uuid()),
    Column(
        _COL_SESSION_ID,
        _UUID_STR,
        ForeignKey(_FK_SESSIONS_ID, ondelete=_ON_DELETE_CASCADE),
        unique=True,
        nullable=False,
    ),
    Column("turn_count", Integer, nullable=False, server_default=_DEFAULT_ZERO),
    Column("round_number", Integer, nullable=False, server_default=_DEFAULT_ZERO),
    Column("scene_number", Integer, nullable=False, server_default=_DEFAULT_ZERO),
    Column("game_clock", Float, nullable=False, server_default="0.0"),
    Column("game_time", _TINY_STR, nullable=False, server_default="morning"),
    Column("conversation_log", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("scene_conversation_log", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("scene_action_log", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("pending_clarification", JSONB, nullable=True),
    Column("world_state", JSONB, nullable=True),
    Column(_COL_CREATED_AT, TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
)

settings = Table(
    "settings",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True, server_default=func.gen_random_uuid()),
    Column(
        _COL_GAME_STATE_ID,
        _UUID_STR,
        _fk_game_state(),
        unique=True,
        nullable=False,
    ),
    Column(_COL_NAME, Text, nullable=False),
    Column("time_period", Text, nullable=False),
    Column("region", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("key_persons", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("key_events", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("locations_data", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("traditions", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("technologies", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("social_structure", Text, nullable=False, server_default=""),
)

players = Table(
    "players",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True, server_default=func.gen_random_uuid()),
    Column(
        _COL_GAME_STATE_ID,
        _UUID_STR,
        _fk_game_state(),
        unique=True,
        nullable=False,
    ),
    Column(_COL_NAME, String(_LEN_LONG), nullable=False, server_default="Player"),
    Column(_COL_LOCATION_ID, Text, nullable=True),
    Column("inventory", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("appearance", Text, nullable=False, server_default=""),
    Column("physical_status", String(_LEN_LONG), nullable=False, server_default="healthy"),
    Column("known_npcs", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("player_event_log", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("learned_facts", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
)

locations = Table(
    "locations",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True),
    Column(
        _COL_GAME_STATE_ID,
        _UUID_STR,
        _fk_game_state(),
        nullable=False,
    ),
    Column(_COL_NAME, Text, nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("parent_location_id", Text, nullable=True),
    Column("location_type", String(_LEN_SHORT), nullable=False, server_default="generic"),
    Column("tags", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("connected_locations", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("npcs_present", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("points_of_interest", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("object_states", JSONB, nullable=False, server_default=_DEFAULT_JSON_OBJECT),
    Index("idx_locations_game_state", _COL_GAME_STATE_ID),
)

npcs = Table(
    "npcs",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True),
    Column(
        _COL_GAME_STATE_ID,
        _UUID_STR,
        _fk_game_state(),
        nullable=False,
    ),
    Column(_COL_NAME, Text, nullable=False),
    Column("biography", Text, nullable=False, server_default=""),
    Column("appearance", Text, nullable=False, server_default=""),
    Column("short_descriptor", Text, nullable=False, server_default=""),
    Column("occupation", Text, nullable=False, server_default=""),
    Column("personality_traits", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("speech_style", Text, nullable=False, server_default=""),
    Column("knowledge_scope", _TINY_STR, nullable=False, server_default="local"),
    Column("attributes", JSONB, nullable=False, server_default=_DEFAULT_JSON_OBJECT),
    Column("inventory", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column(_COL_LOCATION_ID, Text, nullable=True),
    Column("relationships", JSONB, nullable=False, server_default=_DEFAULT_JSON_OBJECT),
    Column("conversation_history", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("current_mood", String(_LEN_SHORT), nullable=False, server_default="neutral"),
    Column("physical_status", String(_LEN_LONG), nullable=False, server_default="healthy"),
    Column("hostility_level", Integer, nullable=False, server_default=_DEFAULT_ZERO),
    Column("recent_hostile_actions", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("life_goal", JSONB, nullable=True),
    Column("tactical_goal", JSONB, nullable=True),
    Index("idx_npcs_game_state", _COL_GAME_STATE_ID),
)

scenes = Table(
    "scenes",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True),
    Column(
        _COL_GAME_STATE_ID,
        _UUID_STR,
        _fk_game_state(),
        nullable=False,
    ),
    Column("is_current", Boolean, nullable=False, server_default="false"),
    Column("scene_number", Integer, nullable=False, server_default=_DEFAULT_ZERO),
    Column(_COL_LOCATION_ID, Text, nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("npcs_present", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("points_of_interest", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("ambient_description", Text, nullable=False, server_default=""),
    Column("time_of_day", _TINY_STR, nullable=False, server_default="day"),
    Column("narrated_text", Text, nullable=False, server_default=""),
    Index("idx_scenes_game_state", _COL_GAME_STATE_ID),
)

knowledge_nodes = Table(
    "knowledge_nodes",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True),
    Column(
        _COL_GAME_STATE_ID,
        _UUID_STR,
        _fk_game_state(),
        nullable=False,
    ),
    Column("content", Text, nullable=False),
    Column("scope", _TINY_STR, nullable=False, server_default="local"),
    Column("source", _TINY_STR, nullable=False, server_default="fact"),
    Column("canon", _TINY_STR, nullable=False, server_default="historical"),
    Column("required_education", Integer, nullable=False, server_default=_DEFAULT_ZERO),
    Column("tags", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column(_COL_LOCATION_ID, Text, nullable=True),
    Column("timestamp", Float, nullable=True),
    Column("salience", Float, nullable=False, server_default="0.5"),
    Column("subject", Text, nullable=True),
    Column("object", Text, nullable=True),
    Column("action", Text, nullable=True),
    Column("outcome", Text, nullable=True),
    Column("subject_id", Text, nullable=True),
    Index("idx_kn_game_state", _COL_GAME_STATE_ID),
    Index("idx_kn_scope", _COL_GAME_STATE_ID, "scope"),
    Index("idx_kn_tags", "tags", postgresql_using="gin"),
)

knowledge_edges = Table(
    "knowledge_edges",
    metadata,
    Column(_COL_ID, Integer, primary_key=True, autoincrement=True),
    Column(
        _COL_GAME_STATE_ID,
        _UUID_STR,
        _fk_game_state(),
        nullable=False,
    ),
    Column("from_node_id", _UUID_STR, nullable=False),
    Column("to_node_id", _UUID_STR, nullable=False),
    Column("edge_type", String(_LEN_SHORT), nullable=False, server_default="related_to"),
    Column("metadata_", JSONB, nullable=False, server_default=_DEFAULT_JSON_OBJECT),
    Index("idx_ke_from", _COL_GAME_STATE_ID, "from_node_id"),
    Index("idx_ke_to", _COL_GAME_STATE_ID, "to_node_id"),
)

ai_call_logs = Table(
    "ai_call_logs",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True, server_default=func.gen_random_uuid()),
    Column(
        _COL_SESSION_ID,
        _UUID_STR,
        ForeignKey(_FK_SESSIONS_ID, ondelete=_ON_DELETE_CASCADE),
        nullable=False,
    ),
    Column(_COL_TURN_NUMBER, Integer, nullable=True),
    Column(_COL_USER_ID, Text, nullable=True),
    Column(_COL_GAME_STATE_ID, _UUID_STR, nullable=True),
    Column("agent_name", String(_LEN_MEDIUM), nullable=False),
    Column("model", String(_LEN_LONG), nullable=False),
    Column("system_prompt", Text, nullable=False),
    Column("messages", JSONB, nullable=False),
    Column("response_content", Text, nullable=False),
    Column("prompt_tokens", Integer, nullable=True),
    Column("completion_tokens", Integer, nullable=True),
    Column("duration_ms", Integer, nullable=True),
    Column("call_sequence", Integer, nullable=True),
    Column("parent_agent", String(_LEN_MEDIUM), nullable=True),
    Column(_COL_CREATED_AT, TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Index("idx_ai_calls_session", _COL_SESSION_ID),
    Index("idx_ai_calls_session_turn", _COL_SESSION_ID, _COL_TURN_NUMBER),
    Index("idx_ai_calls_created", _COL_CREATED_AT),
    Index("idx_ai_calls_user_created", _COL_USER_ID, _COL_CREATED_AT),
    Index("idx_ai_calls_model_created", "model", _COL_CREATED_AT),
    Index("idx_ai_calls_game_state", _COL_GAME_STATE_ID),
)

turn_events = Table(
    "turn_events",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True, server_default=func.gen_random_uuid()),
    Column(
        _COL_SESSION_ID,
        _UUID_STR,
        ForeignKey(_FK_SESSIONS_ID, ondelete=_ON_DELETE_CASCADE),
        nullable=False,
    ),
    Column(_COL_TURN_NUMBER, Integer, nullable=True),
    Column("scene_number", Integer, nullable=True),
    Column("event_type", String(_LEN_SHORT), nullable=False),
    Column("agent_name", String(_LEN_MEDIUM), nullable=True),
    Column("npc_id", _UUID_STR, nullable=True),
    Column("payload", JSONB, nullable=False),
    Column("sequence", Integer, nullable=True),
    Column(_COL_CREATED_AT, TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Index("idx_turn_events_session_turn", _COL_SESSION_ID, _COL_TURN_NUMBER),
    Index("idx_turn_events_session_npc", _COL_SESSION_ID, "npc_id"),
    Index("idx_turn_events_type", "event_type"),
)

game_events = Table(
    "game_events",
    metadata,
    Column(_COL_ID, _UUID_STR, primary_key=True),
    Column(
        _COL_GAME_STATE_ID,
        _UUID_STR,
        _fk_game_state(),
        nullable=False,
    ),
    Column(_COL_NAME, Text, nullable=False),
    Column("scheduled_at", Float, nullable=False),
    Column("duration", Float, nullable=False),
    Column("completes_at", Float, nullable=False),
    Column("status", _TINY_STR, nullable=False, server_default="pending"),
    Column("owner_id", Text, nullable=True),
    Column(_COL_LOCATION_ID, Text, nullable=True),
    Column("scope", _TINY_STR, nullable=False, server_default="local"),
    Column("effects", JSONB, nullable=False, server_default=_DEFAULT_JSON_ARRAY),
    Column("on_complete_description", Text, nullable=False, server_default=""),
    Index("idx_events_game_state", _COL_GAME_STATE_ID),
)

# Key-value store for operator-mutable runtime settings (model overrides, etc.).
# Empty table ⇒ engine falls back to env-var defaults. See db/repo_settings.py.
admin_settings = Table(
    "admin_settings",
    metadata,
    Column("key", Text, primary_key=True),
    Column("provider", Text, nullable=False),
    Column("model_id", Text, nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
)

beta_feedback = Table(
    "beta_feedback",
    metadata,
    _uuid_pk_column(),
    Column("user_id", _UUID_STR, nullable=False),
    Column("user_email", Text, nullable=True),
    Column(
        "game_id",
        _UUID_STR,
        ForeignKey(_FK_GAME_STATES_ID, ondelete=_ON_DELETE_CASCADE),
        nullable=False,
    ),
    Column(_COL_TURN_NUMBER, Integer, nullable=True),
    Column("category", String(_LEN_SHORT), nullable=False),
    Column("message", Text, nullable=False),
    Column(_COL_CREATED_AT, _TZ_TS, nullable=False, server_default=func.now()),
    Index("idx_beta_feedback_created", _COL_CREATED_AT),
    Index("idx_beta_feedback_game", "game_id"),
    Index("idx_beta_feedback_user_created", "user_id", _COL_CREATED_AT),
)
