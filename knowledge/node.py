"""Knowledge node — a single fact, memory, or rumour in the knowledge graph."""

from __future__ import annotations

from enum import Enum, IntEnum
from uuid import UUID

from pydantic import Field

from knowledge import salience as salience_presets
from models.base_model import StorytellerBase

_SALIENCE_LOW = float(0)
_SALIENCE_HIGH = float(1)
_SALIENCE_FIELD = Field(default=salience_presets.DEFAULT, ge=_SALIENCE_LOW, le=_SALIENCE_HIGH)


class KnowledgeScope(IntEnum):
    """How widely a piece of knowledge is known."""

    LOCAL = 1
    CITY = 2
    REGION = 3
    COUNTRY = 4
    WORLD = 5


class KnowledgeSource(Enum):
    """How the knowledge was obtained."""

    FACT = "fact"  # Objectively true
    RUMOR = "rumor"  # May be inaccurate
    PERSONAL_EXPERIENCE = "personal"  # Known from direct experience
    HEARSAY = "hearsay"  # Heard from someone else


class CanonSource(Enum):
    """Whether a node reflects researched history or in-session player actions."""

    HISTORICAL = "historical"  # Wikipedia / DataMiner-sourced "what history says"
    SESSION = "session"  # Player-caused "what happened in this session"


class EdgeType(Enum):
    """Types of relationships between knowledge nodes."""

    WITNESSED = "witnessed"
    TOLD_BY = "told_by"


class KnowledgeNode(StorytellerBase):
    """A single fact / memory in the knowledge graph."""

    text: str
    scope: KnowledgeScope = KnowledgeScope.LOCAL
    source: KnowledgeSource = KnowledgeSource.FACT
    canon: CanonSource = CanonSource.HISTORICAL
    required_education: int = 0  # 0-10
    tags: list[str] = []
    location_id: UUID | None = None
    timestamp: float | None = None  # Game-clock time when learned
    # Per-memory importance — forgettable to life-changing. Combined
    # with recency by ``KnowledgeQueryEngine.get_memories_about`` so a
    # witnessed killing isn't crowded out by trivial chatter.
    salience: float = _SALIENCE_FIELD
