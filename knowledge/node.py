"""Knowledge node — a single fact, memory, or rumour in the knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from models.base_model import BaseModel


class KnowledgeScope(Enum):
    """How widely a piece of knowledge is known."""
    LOCAL = "local"       # Known within a specific location (market stall, tavern)
    CITY = "city"         # Known within a city
    REGION = "region"     # Known within a region
    COUNTRY = "country"   # Known within a country
    WORLD = "world"       # Common / world knowledge

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
    FACT = "fact"                       # Objectively true
    RUMOR = "rumor"                     # May be inaccurate
    PERSONAL_EXPERIENCE = "personal"    # Known from direct experience
    HEARSAY = "hearsay"                 # Heard from someone else


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


class KnowledgeNode(BaseModel):
    """A single fact / memory in the knowledge graph."""

    def __init__(
        self,
        *,
        content: str,
        scope: KnowledgeScope = KnowledgeScope.LOCAL,
        source: KnowledgeSource = KnowledgeSource.FACT,
        required_education: int = 0,
        required_social_status: int = 0,
        tags: list[str] | None = None,
        location_id: str | None = None,
        timestamp: float | None = None,
        confidence: float = 1.0,
    ):
        super().__init__()
        self.content = content
        self.scope = scope
        self.source = source
        self.required_education = required_education      # 0-10
        self.required_social_status = required_social_status  # 0-10
        self.tags: list[str] = tags or []
        self.location_id = location_id
        self.timestamp = timestamp  # Game-clock time when learned
        self.confidence = confidence  # 0.0 – 1.0
