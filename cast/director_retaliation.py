"""NPC retaliation helpers for Director."""

from __future__ import annotations

import asyncio
from typing import Any, NamedTuple

from cast.dice import CombatOutcome, CombatRoll, roll_aggression, roll_combat
from cast.director_context import get_location_name
from models.game_state import GameState

_KEY_GAME_STATE = "game_state"


class RetaliationWork(NamedTuple):
    """Pre-computed data for a single NPC retaliation."""

    npc: Any
    actor: Any
    retaliation_input: str
    aggression: Any
    combat_roll: CombatRoll


class RetaliationHandler:
    """Checks for and executes NPC retaliations after dialogue."""

    def __init__(self, game_state: GameState, actors: dict[str, Any]) -> None:
        self._gs = game_state
        self._actors = actors

    async def check_retaliation(
        self,
        mood_snapshot: dict[str, str],
        skip_uuids: set[str] | None = None,
    ) -> list[dict[str, str]]:
        """Check if any NPC whose mood changed wants to attack.

        ``skip_uuids`` lists NPCs whose dialogue call already resolved a
        combat contest this turn — their mood flip is a direct consequence
        of the combat the Actor already narrated, so a second retaliation
        prompt would be redundant. Typically populated from
        :meth:`DialogueHandler.handle_dialogue`'s combat-engaged set.
        """
        skip = skip_uuids or set()
        retaliated_names = self._seed_retaliated_names(skip)
        work_items = self._collect_work(skip, retaliated_names, mood_snapshot)
        return list(
            await asyncio.gather(
                *(_execute_retaliation(wi, self._gs) for wi in work_items),
            )
        )

    def _seed_retaliated_names(self, skip: set[str]) -> set[str]:
        """Pre-populate the dedup set with skipped NPCs' display names.

        Guarantees that duplicate-name twins (e.g. two "guards") also skip
        the retaliation phase when one of them was already combat-engaged.
        """
        retaliated_names: set[str] = set()
        for skipped_uuid in skip:
            skipped_npc = self._gs.npcs.get(skipped_uuid)
            if skipped_npc:
                retaliated_names.add(skipped_npc.name.lower())
        return retaliated_names

    def _collect_work(
        self,
        skip: set[str],
        retaliated_names: set[str],
        mood_snapshot: dict[str, str],
    ) -> list[RetaliationWork]:
        """Build retaliation work items for every NPC that still qualifies."""
        work_items: list[RetaliationWork] = []
        for npc_uuid, actor in self._actors.items():
            if npc_uuid in skip:
                continue
            work = _build_retaliation_work(npc_uuid, actor, mood_snapshot, retaliated_names, self._gs)
            if work is not None:
                work_items.append(work)
        return work_items


def _build_retaliation_work(
    npc_uuid: str,
    actor: Any,
    mood_snapshot: dict[str, str],
    retaliated_names: set[str],
    game_state: GameState,
) -> RetaliationWork | None:
    """Check if an NPC should retaliate and build work item if so."""
    npc = game_state.npcs.get(npc_uuid)
    if not npc or npc.name.lower() in retaliated_names:
        return None
    if npc.current_mood == mood_snapshot.get(npc_uuid, "neutral"):
        return None

    aggression = roll_aggression(npc.current_mood)
    if aggression is None or not aggression.will_attack:
        return None
    retaliated_names.add(npc.name.lower())

    combat_roll = roll_combat(npc.get_attribute("combat_skill", 3))
    status_hint = ""
    if combat_roll.outcome in (CombatOutcome.ACTOR_SUCCEEDS, CombatOutcome.ACTOR_DOMINATES):
        status_hint = (
            "\nThe NPC is injured. Update their physical status to reflect the injury. "
            "Append [STATUS: <description>] at the end of your response."
        )
    retaliation_input = (
        "{0} retaliates against the player!\n\n"
        "[DICE ROLL: player {1} vs "
        "NPC {2}+{3}]\n"
        "OUTCOME: {4}\n"
        "You MUST narrate this outcome. The NPC attacks FIRST — "
        "they are the aggressor now. Do NOT override the dice result.{5}"
    ).format(
        npc.name,
        combat_roll.player_roll,
        combat_roll.npc_roll,
        combat_roll.npc_bonus,
        combat_roll.description,
        status_hint,
    )
    return RetaliationWork(npc, actor, retaliation_input, aggression, combat_roll)


async def _execute_retaliation(work: RetaliationWork, game_state: GameState) -> dict[str, str]:
    """Execute a single NPC retaliation and return the result entry."""
    response = await work.actor.execute(
        input_data=work.retaliation_input,
        context={
            "npc": work.npc,
            _KEY_GAME_STATE: game_state,
            "location_name": get_location_name(work.npc.location_id, game_state),
        },
    )
    return {
        "npc_name": work.npc.name,
        "response": response,
        "is_retaliation": "true",
        "aggression_roll": "d20: {0} vs threshold {1} (mood: {2}) → attacks".format(
            work.aggression.roll,
            work.aggression.threshold,
            work.aggression.mood,
        ),
        "combat_roll": "d20: player {0} vs NPC {1}+{2} → {3}".format(
            work.combat_roll.player_roll,
            work.combat_roll.npc_roll,
            work.combat_roll.npc_bonus,
            work.combat_roll.outcome.value,
        ),
    }
