"""Typed contract for the outputs of a single Director turn.

``TurnOutputs`` is the payload the :class:`cast.director_execution.PlanExecutor`
hands to the :class:`cast.narrator.Narrator`. It replaces an ad-hoc
``dict[str, Any]`` that previously carried the same fields and was probed
with ``.get(key, default)`` calls scattered across the narrator.

The model is intentionally permissive (every field optional with a sensible
default) so partial turns — a pure wait, a pure scene rebuild, a dialogue-only
continuation — can be constructed without spelling out the empty branches.

Future agents (``WorldChronicler``, ``Critic``) consume the same typed
contract. The ``npc_departures`` field is part of that forward wiring:
the World Chronicler PR introduces it so the upcoming NPC Autonomy PR
only has to populate it from the ``NPCTicker`` output.
"""

from __future__ import annotations

from pydantic import UUID4, BaseModel, ConfigDict, Field

from cast.director_witness import WitnessedAggression
from models.scene import Scene
from models.world_state import WorldThread


class DialogueEntry(BaseModel):
    """One NPC's utterance in response to the player's action.

    ``npc_uuid`` is the canonical reference into ``game_state.npcs`` and
    is what the Narrator uses to gate the player-facing label on
    ``player.known_npcs`` (so an unmet NPC never has their proper name
    leaked into prose). ``npc_name`` carries the NPC's real name for
    internal consumers — the World Chronicler's turn summary, dedup
    fallbacks, and retaliation memory pinning — that legitimately need
    the canonical identifier rather than the gated label.

    ``npc_uuid`` defaults to ``None`` so deterministic fixtures
    (benchmarks, narrator unit tests) can construct entries without a
    real ``GameState`` to back them — :func:`narrator_aliases.resolve_dialogue_npc_label`
    falls back to ``npc_name`` when the uuid is ``None`` or absent from
    the game state. Production producers always set the uuid.

    ``contest_roll`` carries the human-readable combat/contest summary
    that ``cast.director_dialogue`` attaches to dialogue entries when
    the interaction is resolved via a dice roll.
    """

    npc_uuid: UUID4 | None = None
    npc_name: str
    response: str
    contest_roll: str | None = None


class NPCTurnEntry(BaseModel):
    """One NPC's autonomous action on a turn-counting player action.

    ``npc_uuid`` mirrors :class:`DialogueEntry` — it is the gate key the
    Narrator uses to resolve the player-facing label. ``npc_name`` keeps
    the canonical real name for internal consumers (World Chronicler).
    ``npc_uuid`` defaults to ``None`` for the same fixture-friendliness
    reason :class:`DialogueEntry` documents.

    The field name ``action_type`` mirrors the attribute used on
    :class:`cast.npc_turn.NPCTurnAction` and avoids shadowing the
    builtin ``type``.
    """

    npc_uuid: UUID4 | None = None
    npc_name: str
    action: str
    action_type: str


class WaitContext(BaseModel):
    """Structured ambient material surfaced on WAIT turns.

    Populated by :meth:`cast.director_execution.PlanExecutor._refresh_scene_ambience`
    so the Narrator can render real world motion (active threads,
    on-shift NPCs, soon-firing events) instead of the pre-KER-20 stub
    line ``"The player waits and observes the surroundings."``.

    ``active_threads`` carries raw :class:`WorldThread` dataclass
    instances rather than pre-formatted strings so downstream consumers
    (Narrator today, future analytics agents tomorrow) can read the
    structured fields. Pydantic v2 handles dataclass fields natively
    when ``arbitrary_types_allowed`` is set.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    active_threads: list[WorldThread] = Field(default_factory=list)
    on_shift_npcs: list[str] = Field(default_factory=list)
    imminent_events: list[str] = Field(default_factory=list)
    hours_waited: float = Field(default_factory=float)


class TurnOutputs(BaseModel):
    """Typed view of everything produced during a Director turn.

    ``npc_departures`` holds human-readable lines describing NPCs that
    walked out of the current scene between turns (for example
    ``"Marco (bartender) heads off to his quarters for the night"``).
    The World Chronicler PR ships the field dormant — it is populated
    by the upcoming ``NPCTicker`` (PR B, NPC Autonomy), and the Narrator
    already renders each entry so no further plumbing is needed then.

    ``wait_context`` is attached by the PlanExecutor on WAIT turns
    (KER-20) so the Narrator can render grounded ambient prose instead
    of a hard-coded stub. Non-WAIT turns leave it ``None``.

    ``witnessed_events`` carries proximity-witness records for
    aggressive player actions against inanimate targets (KER-18). The
    field is populated inside the object-interaction branch of
    :class:`cast.director_execution.PlanExecutor` and consumed by
    :class:`cast.npc_turn.NPCTurnResolver` to inject an incident clause
    into the guard NPC-turn prompt. It is intentionally **not** rendered
    by the Narrator — the guard reaction surfaces via ``npc_turns`` and
    the object outcome surfaces via ``object_interactions``, so a
    separate ``witnessed_events`` render path would duplicate both.

    ``intent`` is the player's stated goal for the turn, surfaced by the
    Director routing plan (KER-19). The Narrator honors it in narration
    and explicitly acknowledges a contradiction when the raw material
    drifts from the stated goal.
    """

    wait: bool = False
    wait_reason: str | None = None
    wait_context: WaitContext | None = None
    scene: Scene | None = None
    new_npcs: list[str] = Field(default_factory=list)
    dialogue: list[DialogueEntry] = Field(default_factory=list)
    item_examination: list[str] = Field(default_factory=list)
    object_interactions: list[str] = Field(default_factory=list)
    npc_turns: list[NPCTurnEntry] = Field(default_factory=list)
    npc_departures: list[str] = Field(default_factory=list)
    completed_events: list[str] = Field(default_factory=list)
    witnessed_events: list[WitnessedAggression] = Field(default_factory=list)
    intent: str | None = None
