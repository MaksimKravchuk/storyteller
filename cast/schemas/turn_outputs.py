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

from pydantic import BaseModel, Field

from cast.director_witness import WitnessedAggression
from models.scene import Scene


class DialogueEntry(BaseModel):
    """One NPC's utterance in response to the player's action.

    ``contest_roll`` carries the human-readable combat/contest summary
    that ``cast.director_dialogue`` attaches to dialogue entries when
    the interaction is resolved via a dice roll.
    """

    npc_name: str
    response: str
    contest_roll: str | None = None


class NPCTurnEntry(BaseModel):
    """One NPC's autonomous action on a turn-counting player action.

    The field name ``action_type`` mirrors the attribute used on
    :class:`cast.npc_turn.NPCTurnAction` and avoids shadowing the
    builtin ``type``.
    """

    npc_name: str
    action: str
    action_type: str


class TurnOutputs(BaseModel):
    """Typed view of everything produced during a Director turn.

    ``npc_departures`` holds human-readable lines describing NPCs that
    walked out of the current scene between turns (for example
    ``"Marco (bartender) heads off to his quarters for the night"``).
    The World Chronicler PR ships the field dormant — it is populated
    by the upcoming ``NPCTicker`` (PR B, NPC Autonomy), and the Narrator
    already renders each entry so no further plumbing is needed then.

    ``witnessed_events`` carries proximity-witness records for
    aggressive player actions against inanimate targets (KER-18). The
    field is populated inside the object-interaction branch of
    :class:`cast.director_execution.PlanExecutor` and consumed by
    :class:`cast.npc_turn.NPCTurnResolver` to inject an incident clause
    into the guard NPC-turn prompt. It is intentionally **not** rendered
    by the Narrator — the guard reaction surfaces via ``npc_turns`` and
    the object outcome surfaces via ``object_interactions``, so a
    separate ``witnessed_events`` render path would duplicate both.
    """

    wait: bool = False
    wait_reason: str | None = None
    scene: Scene | None = None
    new_npcs: list[str] = Field(default_factory=list)
    dialogue: list[DialogueEntry] = Field(default_factory=list)
    item_examination: list[str] = Field(default_factory=list)
    object_interactions: list[str] = Field(default_factory=list)
    npc_turns: list[NPCTurnEntry] = Field(default_factory=list)
    npc_departures: list[str] = Field(default_factory=list)
    completed_events: list[str] = Field(default_factory=list)
    witnessed_events: list[WitnessedAggression] = Field(default_factory=list)
