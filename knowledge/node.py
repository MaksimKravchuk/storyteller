"""Knowledge node — a single fact, memory, or rumour in the knowledge graph."""

from __future__ import annotations

from enum import Enum

from models.base_model import StorytellerBase


class KnowledgeScope(Enum):
    """How widely a piece of knowledge is known."""

    LOCAL = "local"  # Known within a specific location (market stall, tavern)
    CITY = "city"  # Known within a city
    REGION = "region"  # Known within a region
    COUNTRY = "country"  # Known within a country
    WORLD = "world"  # Common / world knowledge

    def __le__(self, other: KnowledgeScope) -> bool:
        order = list(KnowledgeScope)
        return order.index(self) <= order.index(other)

    def __lt__(self, other: KnowledgeScope) -> bool:
        order = list(KnowledgeScope)
        return order.index(self) < order.index(other)

    def __ge__(self, other: KnowledgeScope) -> bool:
        order = list(KnowledgeScope)
        return order.index(self) >= order.index(other)

    def __gt__(self, other: KnowledgeScope) -> bool:
        order = list(KnowledgeScope)
        return order.index(self) > order.index(other)


class KnowledgeSource(Enum):
    """How the knowledge was obtained."""

    FACT = "fact"  # Objectively true
    RUMOR = "rumor"  # May be inaccurate
    PERSONAL_EXPERIENCE = "personal"  # Known from direct experience
    HEARSAY = "hearsay"  # Heard from someone else


class EdgeType(Enum):
    """Types of relationships between knowledge nodes."""

    LOCATED_IN = "located_in"
    KNOWS_ABOUT = "knows_about"
    RELATED_TO = "related_to"
    PART_OF = "part_of"
    WITNESSED = "witnessed"
    TOLD_BY = "told_by"
    CONTRADICTS = "contradicts"
    OWNED_BY = "owned_by"


class KnowledgeNode(StorytellerBase):
    """A single fact / memory in the knowledge graph."""

    text: str
    scope: KnowledgeScope = KnowledgeScope.LOCAL
    source: KnowledgeSource = KnowledgeSource.FACT
    required_education: int = 0  # 0-10
    required_social_status: int = 0  # 0-10
    tags: list[str] = []
    location_id: str | None = None
    timestamp: float | None = None  # Game-clock time when learned
    confidence: float = 1.0  # 0.0 – 1.0
