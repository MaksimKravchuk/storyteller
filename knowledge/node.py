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
    """A single fact / memory in the knowledge graph.

    The free-text ``text`` is the primary display surface — the
    ``subject``/``object``/``action``/``outcome`` slots are optional
    structured metadata for downstream dedup, querying, and contradiction
    detection. They are populated at creation sites where the data is
    cheap to extract (combat, dialogue, effect-driven events) and left
    ``None`` everywhere else (Wikipedia facts, scene-state deltas,
    forwarded hearsay). ``subject_id`` is the *canonical UUID* of the
    entity the memory is about — distinct from the free-text ``subject``
    name and from the WITNESSED edge — and may be backfilled later by
    :meth:`KnowledgeGraph.resolve_subject_identity` once an identity is
    learned.
    """

    text: str
    scope: KnowledgeScope = KnowledgeScope.LOCAL
    source: KnowledgeSource = KnowledgeSource.FACT
    canon: CanonSource = CanonSource.HISTORICAL
    required_education: int = 0  # 0-10
    tags: list[str] = []
    location_id: UUID | None = None
    timestamp: float | None = None  # Game-clock time when learned
    salience: float = _SALIENCE_FIELD
    subject: str | None = None
    object: str | None = None
    action: str | None = None
    outcome: str | None = None
    subject_id: UUID | None = None
