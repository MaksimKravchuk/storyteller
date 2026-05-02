"""Knowledge node — a single fact, memory, or rumour in the knowledge graph."""

from __future__ import annotations

from enum import Enum, IntEnum
from uuid import UUID

from models.base_model import StorytellerBase


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
