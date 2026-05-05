"""Schemas for AnachronismClassifier output and per-NPC modifier results."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

# Width of the strangeness axis. Mirrored in the prompt template so
# the LLM's clamp matches the schema's clamp; surfaced as a constant
# so dependent math (modifier scaling, prompt rendering) shares one
# source of truth.
STRANGENESS_MIN = 0
STRANGENESS_MAX = 10


class AnachronismClassification(BaseModel):
    """LLM verdict on whether a player action is out of period.

    ``strangeness_score`` is the 0-10 base axis the modifier in
    :mod:`cast.anachronism` scales by per-NPC education and the
    familiarity-discount counter. ``unfamiliar_concepts`` carries the
    snake_case concept slugs the classifier matched against the seed
    pool (or invented when no seed fit) — they are the join key for
    :func:`knowledge.query.KnowledgeQueryEngine.get_memories_about_concept`,
    so two encounters with the same concept on the same NPC discount
    the second roll. ``perceived_rewrite`` is the in-period framing of
    the action that is threaded into the Actor's prompt body and the
    DialogueEntry the Narrator reads — without it the dice say
    bewildered, the narration says bewildered, and the NPC's quote
    still says ``halt, citizen!``.

    ``extra="forbid"`` so a schema-drifted LLM (e.g. emitting
    ``"score"`` instead of ``"strangeness_score"``) fails loudly into
    the retry path rather than silently producing a zero.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    strangeness_score: int = Field(ge=STRANGENESS_MIN, le=STRANGENESS_MAX)
    unfamiliar_concepts: list[str] = Field(default_factory=list)
    perceived_rewrite: str = ""


@dataclass(frozen=True)
class NPCAnachronismResult:
    """Per-NPC view of the turn's classification, modulated by NPC state.

    ``base`` is the same :class:`AnachronismClassification` every NPC
    in the turn sees. ``effective_strangeness`` is the post-modifier
    integer the dice contest reads — a scholar (``education=8``)
    discounts the base; a peasant (``education=2``) amplifies it; an
    NPC who has met the same concept before discounts further. Clamped
    to ``[0, 10]`` so an extreme combination cannot wrap the dice
    bonus into nonsense.

    ``encounter_count`` is the number of prior memories this NPC has
    holding any of the unfamiliar concepts. Stored on the result so
    the dice telemetry can record *why* the modifier landed where it
    did, not just the final value.
    """

    base: AnachronismClassification
    effective_strangeness: int
    encounter_count: int

    @property
    def perceived_rewrite(self) -> str:
        """Convenience pass-through — the NPC sees the same rewrite as everyone else."""
        return self.base.perceived_rewrite

    @property
    def unfamiliar_concepts(self) -> list[str]:
        """Convenience pass-through — concept tags are turn-wide, not per-NPC."""
        return list(self.base.unfamiliar_concepts)
