"""Dialogue routing helpers for Director."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from cast import (
    director_context,
    director_dialogue_helpers as dlg_helpers,
    director_dialogue_witness,
    known_npcs,
)
from cast.dice import ContestRoll, ContestType
from knowledge import salience as salience_presets
from knowledge.memory import MemoryManager
from knowledge.memory_slots import MemorySlots
from models.game_state import GameState

_KEY_GAME_STATE = "game_state"

# Convenience alias for dialogue result entries to keep annotations shallow.
DialogueEntry = dict[str, str]
DialogueResult = tuple[list[DialogueEntry], set[UUID]]


def _snpc_matches(snpc: Any, targets_lower: set[str], game_state: GameState) -> bool:
    """Check whether a single SceneNPC matches any of the target names."""
    if snpc.uuid is None or snpc.uuid not in game_state.npcs:
        return False
    npc = game_state.npcs[snpc.uuid]
    return snpc.role.lower() in targets_lower or npc.name.lower() in targets_lower


def _known_scene_identifiers(scene: Any, game_state: GameState) -> set[str]:
    """Return lowercase roles and names of NPCs already in the scene."""
    npcs = game_state.npcs
    known = {snpc.role.lower() for snpc in scene.npcs_present}
    for snpc in scene.npcs_present:
        if snpc.uuid and snpc.uuid in npcs:
            known.add(npcs[snpc.uuid].name.lower())
    return known


async def _execute_npc_dialogue(
    npc: Any,
    actor: Any,
    action_text: str,
    contest_roll: ContestRoll | None,
    game_state: GameState,
) -> dict[str, str]:
    """Execute a single NPC dialogue and return the result entry."""
    reply = await actor.execute(
        input_data=action_text,
        context={
            "npc": npc,
            _KEY_GAME_STATE: game_state,
            "location_name": director_context.get_location_name(npc.location_id, game_state),
        },
    )
    known_npcs.apply_revealed_reply(reply, npc.uuid, game_state)
    result_entry: dict[str, str] = {
        "npc_uuid": npc.uuid,
        "npc_name": npc.name,
        "response": reply.text,
    }
    if contest_roll:
        actor_total = "{0}+{1}".format(contest_roll.actor_roll, contest_roll.actor_bonus)
        target_total = "{0}+{1}".format(contest_roll.target_roll, contest_roll.target_bonus)
        outcome = contest_roll.outcome.value
        result_entry["contest_roll"] = "d20: actor {0} vs target {1} → {2}".format(
            actor_total,
            target_total,
            outcome,
        )
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


async def _expand_npc_inventories(
    new_cards: list[Any],
    item_generator: Any,
    game_state: GameState,
) -> None:
    """Use the ItemGenerator to upgrade bare inventory strings on new NPCs."""
    await asyncio.gather(*(_expand_single_inventory(card, item_generator, game_state) for card in new_cards))


# ---------------------------------------------------------------------------
# DialogueHandler class (≤7 methods including __init__)
# ---------------------------------------------------------------------------


class DialogueHandler:
    """Routes dialogue to Actor agents and manages scene NPCs."""

    def __init__(
        self,
        game_state: GameState,
        actors: dict[UUID, Any],
        memory_manager: MemoryManager,
    ) -> None:
        self._gs = game_state
        self._actors = actors
        self._memory_manager = memory_manager

    async def handle_dialogue(
        self,
        player_action: str,
        target_names: list[str],
        is_aggressive: bool = False,
        contest_info: dict | None = None,
    ) -> DialogueResult:
        """Route dialogue to the correct Actor agents.

        After the dialogue turn resolves, each *targeted* NPC gets a
        long-term memory node summarising the exchange, produced via the
        LLM summariser. Every other initialised NPC in the current scene
        (the co-witnesses — NPCs who were standing right there and
        would logically overhear the conversation) is then given a
        zero-LLM-cost ``PERSONAL_EXPERIENCE`` memory containing the raw
        overheard transcript (KER-11). Summarisation is awaited before
        returning so every memory is in the graph before the next
        Actor call reads them back via ``get_memories_held_by``.

        LLM call budget per TALK turn: ``N_targeted`` summariser calls
        (unchanged from before KER-11) — co-witness broadcast is
        deterministic and does not touch the LLM.

        Returns a tuple ``(entries, combat_engaged_uuids)`` where
        ``combat_engaged_uuids`` is the set of NPC UUIDs whose dialogue call
        carried a *combat* contest roll this turn. Callers pass this set to
        :meth:`RetaliationHandler.check_retaliation` so the same NPC is not
        sent a redundant retaliation prompt — the combat dice in the
        dialogue call already resolved the aggression.
        """
        work_items = self._collect_targets(target_names, player_action, is_aggressive, contest_info)
        dialogue_entries = list(
            await asyncio.gather(*(_execute_npc_dialogue(*wi, self._gs) for wi in work_items)),
        )
        dlg_helpers.append_conversation_history(work_items, dialogue_entries, player_action)
        scene = self._gs.current_scene
        await self._memory_manager.summarize_interactions_batch(
            dlg_helpers.format_dialogue_summary_pairs(
                work_items,
                dialogue_entries,
                player_action,
                player_name=self._gs.player.name,
            ),
            self._gs.game_clock,
            location_id=scene.location_id if scene else None,
            subject_id=self._gs.player.uuid,
        )
        await director_dialogue_witness.broadcast_cowitness_memories(
            work_items,
            dialogue_entries,
            player_action,
            self._gs,
            self._memory_manager,
        )
        combat_engaged_uuids = {
            work_item[0].uuid
            for work_item in work_items
            if work_item[3] is not None and work_item[3].contest_type == ContestType.COMBAT
        }
        return dialogue_entries, combat_engaged_uuids

    def targets_match_scene_npcs(self, target_names: list[str]) -> bool:
        """Return True if any target name matches an initialised SceneNPC."""
        scene = self._gs.current_scene
        if not scene or not target_names:
            return False
        targets_lower = {target.lower() for target in target_names}
        return any(_snpc_matches(snpc, targets_lower, self._gs) for snpc in scene.npcs_present)

    def ensure_targets_in_scene(self, target_names: list[str]) -> None:
        """Make sure every target is represented as a SceneNPC."""
        from models.scene import SceneNPC

        scene = self._gs.current_scene
        if not scene:
            return
        known = _known_scene_identifiers(scene, self._gs)
        for target in target_names:
            if target.lower() not in known:
                scene.npcs_present.append(SceneNPC(role=target))

    async def init_scene_npcs(
        self,
        npc_generator: Any,
        register_fn: Any,
        item_generator: Any | None = None,
    ) -> list[Any]:
        """Initialise any SceneNPC objects that need full NPCCard + Actor."""
        scene = self._gs.current_scene
        if not scene:
            return []
        uninit = [snpc for snpc in scene.npcs_present if snpc.uuid is None]
        if not uninit:
            return []
        new_cards = await npc_generator.execute(
            input_data=[snpc.role for snpc in uninit],
            context={_KEY_GAME_STATE: self._gs},
        )

        if item_generator:
            await _expand_npc_inventories(new_cards, item_generator, self._gs)

        for scene_npc, card in zip(uninit, new_cards):
            register_fn(card)
            scene_npc.uuid = card.uuid
        return list(new_cards)

    async def summarize_retaliations(
        self,
        retaliation_entries: list[dict[str, Any]],
        player_action: str,
    ) -> None:
        """Persist a WITNESSED memory node for each retaliating NPC.

        ``RetaliationHandler`` produces one entry per NPC whose mood
        flipped into an attack this turn. Each entry carries an
        ``npc_uuid`` key — also surfaced on :class:`DialogueEntry` for
        the Narrator's known-name gating — that pins the resulting
        memory to the retaliator. Without this, a subsequent
        ``get_memories_held_by(retaliator)`` would return nothing about
        the fight.

        The interaction log is prefixed with ``[retaliation]`` so the
        summariser — and any downstream prompt that inspects the raw
        log — can distinguish provoked combat from targeted combat.
        """
        from knowledge.memory import DialoguePair

        player_name = self._gs.player.name
        pairs: list[DialoguePair] = [
            (
                entry["npc_uuid"],
                "[retaliation] Player: {0}\n{1}: {2}".format(
                    player_action,
                    entry.get("npc_name", ""),
                    entry.get("response", ""),
                ),
                MemorySlots(
                    subject=entry.get("npc_name", "") or None,
                    object=player_name,
                    action="retaliated_against",
                ),
            )
            for entry in retaliation_entries
            if entry.get("npc_uuid")
        ]
        scene = self._gs.current_scene
        await self._memory_manager.summarize_interactions_batch(
            pairs,
            self._gs.game_clock,
            location_id=scene.location_id if scene else None,
            salience=salience_presets.RETALIATION,
            subject_id=self._gs.player.uuid,
        )

    def _collect_targets(
        self,
        target_names: list[str],
        player_action: str,
        is_aggressive: bool,
        contest_info: dict | None = None,
    ) -> list[tuple[Any, Any, str, ContestRoll | None]]:
        """Match target names to NPCs and prepare dialogue work items."""
        matched_uuids = dlg_helpers.resolve_target_uuids(target_names, self._gs)
        return [
            (
                self._gs.npcs[uid],
                self._actors[uid],
                *dlg_helpers.build_contested_action(
                    player_action,
                    self._gs.npcs[uid],
                    is_aggressive,
                    contest_info,
                ),
            )
            for uid in matched_uuids
            if uid in self._actors
        ]
