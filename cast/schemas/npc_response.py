"""Schema for the NPC-generator LLM JSON response."""

from __future__ import annotations

from pydantic import BaseModel, Field

from models.goal import GoalKind


class NPCGoalDraft(BaseModel):
    """Optional life-tier goal block the LLM may attach to a generated NPC.

    Restrained to KILL / PURSUE / PROTECT — the kinds that read as
    "standing intent driven by biography". The other ``GoalKind`` values
    (ACQUIRE, FLEE, plus the tactical-tier kinds like DEFEND/EAT) are
    excluded by prompt convention; the schema accepts the full enum and
    the applier in :class:`cast.npc_generator.NPCGenerator` filters out
    unfit kinds rather than failing the whole response.

    ``target_name`` is a free-form name string the LLM picks from the
    list of existing NPCs handed to it via ``candidate_targets``; the
    applier resolves the case-insensitive match against
    ``game_state.npcs`` and drops the goal if no NPC matches, logging
    a warning so a sustained miss-rate signals a prompt regression.
    """

    kind: GoalKind
    description: str
    target_name: str | None = None


class NPCAttributes(BaseModel):
    """Fixed-key NPC skill/stat block the LLM fills in.

    Strict-mode structured outputs reject free-form ``dict[str, int]``
    because ``_StrictSchemaNormalizer`` only anchors
    ``additionalProperties: false`` onto nodes that expose explicit
    ``properties``. Enumerating the keys as typed fields gives the
    normalizer something to clamp; the set mirrors the NPC-generator
    prompt, which specifies a 0-10 scale.
    """

    education: int = Field(default=0, ge=0, le=10)
    social_status: int = Field(default=0, ge=0, le=10)
    friendliness: int = Field(default=0, ge=0, le=10)
    suspicion: int = Field(default=0, ge=0, le=10)
    combat_skill: int = Field(default=0, ge=0, le=10)
    persuasion_skill: int = Field(default=0, ge=0, le=10)
    deception_skill: int = Field(default=0, ge=0, le=10)
    intimidation_skill: int = Field(default=0, ge=0, le=10)
    perception_skill: int = Field(default=0, ge=0, le=10)
    stealth_skill: int = Field(default=0, ge=0, le=10)


class NPCResponse(BaseModel):
    """Typed view of the fields the LLM produces for a single NPC card.

    Field defaults mirror the ``.get(key, default)`` semantics of the
    original ``cast/npc_generator.py`` code. ``uuid`` and ``location_id``
    are intentionally absent — those are stamped by the generator
    caller from the current game state, not by the LLM.

    ``goal`` is the optional life-tier goal draft (see
    :class:`NPCGoalDraft`). Default ``None`` so silent NPCs stay silent;
    the prompt's restraint clause keeps emission rare and the applier
    rate-limits to one goal per batch.
    """

    name: str = "Unknown"
    biography: str = ""
    appearance: str = ""
    short_descriptor: str = ""
    occupation: str = ""
    personality_traits: list[str] = Field(default_factory=list)
    speech_style: str = "neutral"
    knowledge_scope: str = "local"
    attributes: NPCAttributes = Field(default_factory=NPCAttributes)
    inventory: list[str] = Field(default_factory=list)
    goal: NPCGoalDraft | None = None
