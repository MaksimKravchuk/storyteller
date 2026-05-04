"""Pure worker helpers for dialogue routing.

Lives outside :mod:`cast.director_dialogue` so that module stays
under the WPS201/WPS202 import + module-member budgets while these
helpers (work-item construction, dialogue-entry decoration, the
single-NPC Actor call, scene-NPC lookup) remain easy to unit test.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, NamedTuple

from cast import director_context, director_dialogue_helpers as dlg_helpers, known_npcs

if TYPE_CHECKING:
    from cast.anachronism import TurnAnachronismContext
    from cast.dice import ContestRoll
    from cast.schemas.anachronism import NPCAnachronismResult
    from models.game_state import GameState


_KEY_GAME_STATE = "game_state"


# Convenience alias for dialogue result entries; widened to ``Any`` because
# every entry carries strings (npc_name, response, …) plus UUIDs and lists.
DialogueEntry = dict[str, Any]


class WorkItem(NamedTuple):
    """Per-NPC dialogue work item.

    NamedTuple keeps positional indexing (``wi[0]``) for the
    co-witness / summariser helpers that still index by slot, while
    the named fields give mypy a precise per-element type instead of
    the union you get from a bare tuple alias.
    """

    npc: Any
    actor: Any
    action_text: str
    contest_roll: ContestRoll | None
    anachronism: NPCAnachronismResult | None


async def execute_npc_dialogue(work: WorkItem, game_state: GameState) -> DialogueEntry:
    """Execute a single NPC dialogue and return the result entry.

    The optional contest-roll and anachronism decorations are inlined
    because the surrounding module is already at the WPS202 module-
    member ceiling — extracting them would push us over.
    """
    reply = await work.actor.execute(
        input_data=work.action_text,
        context={
            "npc": work.npc,
            _KEY_GAME_STATE: game_state,
            "location_name": director_context.get_location_name(work.npc.location_id, game_state),
        },
    )
    known_npcs.apply_revealed_reply(reply, work.npc.uuid, game_state)
    result_entry: DialogueEntry = {
        "npc_uuid": work.npc.uuid,
        "npc_name": work.npc.name,
        "response": reply.text,
    }
    roll = work.contest_roll
    if roll is not None:
        result_entry["contest_roll"] = "d20: actor {0}+{1} vs target {2}+{3} → {4}".format(
            roll.actor_roll,
            roll.actor_bonus,
            roll.target_roll,
            roll.target_bonus,
            roll.outcome.value,
        )
    anach = work.anachronism
    if anach is not None and anach.base.strangeness_score > 0:
        result_entry["unfamiliar_concepts"] = list(anach.unfamiliar_concepts)
        result_entry["perceived_rewrite"] = anach.perceived_rewrite
    return result_entry


async def _expand_single_inventory(card: Any, item_generator: Any, game_state: GameState) -> None:
    """Expand one NPC's bare inventory strings via the ItemGenerator."""
    if not card.inventory:
        return
    owner_ctx = "{0}, {1}".format(card.name, card.occupation)
    card.inventory = await item_generator.execute(
        input_data=card.inventory,
        context={
            "mode": "batch",
            _KEY_GAME_STATE: game_state,
            "owner_context": owner_ctx,
        },
    )


async def expand_npc_inventories(
    new_cards: list[Any],
    item_generator: Any,
    game_state: GameState,
) -> None:
    """Use the ItemGenerator to upgrade bare inventory strings on new NPCs."""
    await asyncio.gather(*(_expand_single_inventory(card, item_generator, game_state) for card in new_cards))


def build_work_item(
    target: tuple[Any, Any],
    player_action: str,
    contest_info: dict | None,
    is_aggressive: bool,
    anachronism_ctx: TurnAnachronismContext | None,
) -> WorkItem:
    """Assemble one dialogue work item with optional anachronism modulation.

    *target* is the ``(npc, actor)`` pair the caller already has on
    hand; bundling them keeps the signature inside the WPS211 budget
    without losing the per-NPC routing that the dice contest reads.
    """
    npc, actor = target
    per_npc = None if anachronism_ctx is None else anachronism_ctx.for_npc(npc)
    action_text, contest_roll = dlg_helpers.build_contested_action(
        player_action,
        npc,
        dlg_helpers.ContestRequest(is_aggressive=is_aggressive, contest_info=contest_info),
        anachronism=per_npc,
    )
    return WorkItem(
        npc=npc,
        actor=actor,
        action_text=action_text,
        contest_roll=contest_roll,
        anachronism=per_npc,
    )
