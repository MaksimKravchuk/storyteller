"""Plan execution helpers for Director."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from cast.constants import SCENE_CHANGING_ACTIONS, TURN_COUNTING_ACTIONS
from cast.director_dialogue import DialogueHandler
from cast.director_events import EventProcessor
from cast.director_retaliation import RetaliationHandler
from cast.npc_turn import NPCTurnResolver
from models.game_state import GameState
from timeline.event import GameEvent

_KEY_PLAYER_ACTION = "player_action"
_KEY_ACTION_TYPE = "action_type"
_KEY_GAME_STATE = "game_state"
_DEFAULT_ACTION = "OTHER"

_SCENE_DESC_PREVIEW = 200


def _snapshot_moods(npcs: dict) -> dict[str, str]:
    """Capture current mood of every NPC by UUID."""
    return {uuid: npc.current_mood for uuid, npc in npcs.items()}


def _filter_item_targets(targets: list[str], npcs: dict) -> list[str]:
    """Return targets that are NOT NPC names (i.e. likely items/objects)."""
    npc_names_lower = {npc.name.lower() for npc in npcs.values()}
    return [target for target in targets if target.lower() not in npc_names_lower]


def _filter_known_npc_targets(targets: list[str], game_state: GameState) -> list[str]:
    """Keep only targets that match an NPC already known in the scene or game state."""
    scene = game_state.current_scene
    npcs = game_state.npcs

    known: set[str] = set()
    for npc in npcs.values():
        known.add(npc.name.lower())
        if hasattr(npc, "occupation") and npc.occupation:
            known.add(npc.occupation.lower())
    if scene:
        for snpc in scene.npcs_present:
            known.add(snpc.role.lower())

    return [target for target in targets if target.lower() in known]


def _ensure_npc_targets_in_scene(
    plan: dict,
    target_names: list[str],
    game_state: GameState,
    dlg: Any,
) -> None:
    """Filter targets and ensure NPC ones are represented in the scene.

    Only creates new SceneNPCs for unknown targets when the Director
    explicitly requested npc_generator.  Otherwise item names like
    "меч" get mistakenly turned into NPCs.
    """
    npc_targets = (
        target_names
        if "npc_generator" in plan.get("delegate_to", [])
        else _filter_known_npc_targets(target_names, game_state)
    )
    dlg.ensure_targets_in_scene(npc_targets)


@dataclass
class _Agents:
    """Bundle of sub-agents used by PlanExecutor."""

    events: EventProcessor
    dialogue: DialogueHandler
    retaliation: RetaliationHandler
    npc_turns: NPCTurnResolver


class PlanExecutor:
    """Executes a routing plan by coordinating sub-agents."""

    def __init__(
        self,
        game_state: GameState,
        agents: _Agents,
        cast: Any,
        register_npc_fn: Any,
    ) -> None:
        self._gs = game_state
        self._agents = agents
        self._cast = cast
        self._register_npc = register_npc_fn

    async def execute_plan(
        self,
        plan: dict,
        player_action: str,
        completed_events: list[GameEvent],
    ) -> str:
        """Delegate to agents based on the routing plan and assemble output."""
        raw_outputs: dict[str, Any] = {}
        action_type = plan.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION)

        local_events = await self._process_events(completed_events)

        if action_type == "WAIT":
            raw_outputs["wait"] = True
            if plan.get("wait_reason"):
                raw_outputs["wait_reason"] = plan["wait_reason"]
        else:
            await self._prepare_scene(
                plan.get("delegate_to", []),
                action_type,
                plan.get("targets", []),
                player_action,
                raw_outputs,
            )
            await self._process_target_npcs(plan, player_action, raw_outputs)

            if action_type == "EXAMINE":
                item_desc = await self._examine_items(plan.get("targets", []), player_action)
                if item_desc:
                    raw_outputs["item_examination"] = item_desc

        if local_events:
            raw_outputs["completed_events"] = [ev.on_complete_description or ev.name for ev in local_events]

        await self._resolve_npc_turns(action_type, player_action, raw_outputs)

        return await self._cast.narrator.execute(
            input_data=raw_outputs,
            context={
                _KEY_PLAYER_ACTION: player_action,
                _KEY_GAME_STATE: self._gs,
                "scene_history": self._gs.scene_conversation_log[-5:],
            },
        )

    async def _resolve_npc_turns(
        self,
        action_type: str,
        player_action: str,
        raw_outputs: dict[str, Any],
    ) -> None:
        """Resolve NPC autonomous turns for turn-counting actions."""
        if action_type not in TURN_COUNTING_ACTIONS:
            return
        npc_actions = await self._agents.npc_turns.resolve_npc_turns(player_action)
        if npc_actions:
            raw_outputs["npc_turns"] = [
                {"npc_name": npc_act.npc_name, "action": npc_act.action_description, "type": npc_act.action_type}
                for npc_act in npc_actions
            ]

    async def _process_events(self, completed_events: list[GameEvent]) -> list[GameEvent]:
        """Partition events, process remote ones, return local events."""
        local, remote = self._agents.events.partition_events(completed_events)
        if remote:
            await self._agents.events.process_remote_events(remote)
        return local

    async def _process_target_npcs(self, plan: dict, player_action: str, raw_outputs: dict[str, Any]) -> None:
        """Ensure targeted NPCs exist in the scene, run interactions."""
        dlg = self._agents.dialogue
        target_names = plan.get("targets", [])
        if target_names:
            _ensure_npc_targets_in_scene(plan, target_names, self._gs, dlg)
            new_npcs = await dlg.init_scene_npcs(
                self._cast.npc_generator,
                self._register_npc,
                self._cast.item_generator,
            )
            if new_npcs:
                raw_outputs["new_npcs"] = ["{0} ({1})".format(npc.name, npc.occupation) for npc in new_npcs]

        should_talk = dlg.targets_match_scene_npcs(target_names) or "actor" in plan.get("delegate_to", [])
        if should_talk or plan.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION) == "TALK":
            contest_info = plan.get("contest")
            await self._run_interactions(
                player_action,
                target_names,
                bool(plan.get("is_aggressive")),
                raw_outputs,
                contest_info,
            )

    async def _prepare_scene(
        self,
        delegates: list[str],
        action_type: str,
        targets: list[str],
        player_action: str,
        raw_outputs: dict[str, Any],
    ) -> None:
        """Build scene if needed and initialise any uninitialised NPCs."""
        needs_rebuild = "scene_builder" in delegates or action_type in SCENE_CHANGING_ACTIONS
        # Skip rebuild when MOVE targets are all NPCs already in the scene
        # (e.g. "walk to the guard" — no location change).
        if needs_rebuild and action_type == "MOVE" and targets:
            known = _filter_known_npc_targets(targets, self._gs)
            if len(known) == len(targets):
                needs_rebuild = False
        if needs_rebuild:
            scene = await self._cast.scene_builder.execute(
                input_data=player_action,
                context={_KEY_GAME_STATE: self._gs},
            )
            raw_outputs["scene"] = scene
            self._gs.current_scene = scene
            self._gs.scene_number += 1
            self._gs.scene_conversation_log = []

        await self._agents.dialogue.init_scene_npcs(
            self._cast.npc_generator,
            self._register_npc,
            self._cast.item_generator,
        )

    async def _examine_items(self, targets: list[str], player_action: str) -> list[str]:
        """Examine items from scene or NPC inventories via the ItemGenerator."""
        item_targets = _filter_item_targets(targets, self._gs.npcs)
        if not item_targets or not self._cast.item_generator:
            return []

        scene = self._gs.current_scene
        hint = scene.description[:_SCENE_DESC_PREVIEW] if scene else "unknown location"

        return list(
            await asyncio.gather(
                *(
                    self._cast.item_generator.execute(
                        input_data=name,
                        context={"mode": "examine", _KEY_GAME_STATE: self._gs, "context_hint": hint},
                    )
                    for name in item_targets
                )
            )
        )

    async def _run_interactions(
        self,
        player_action: str,
        target_names: list[str],
        is_aggressive: bool,
        raw_outputs: dict[str, Any],
        contest_info: dict | None = None,
    ) -> None:
        """Run NPC dialogue and retaliation checks."""
        mood_snapshot = _snapshot_moods(self._gs.npcs)

        dlg = self._agents.dialogue
        dialogue_entries = await dlg.handle_dialogue(
            player_action,
            target_names,
            is_aggressive=is_aggressive,
            contest_info=contest_info,
        )
        if dialogue_entries:
            raw_outputs["dialogue"] = dialogue_entries

        retaliation_entries = await self._agents.retaliation.check_retaliation(mood_snapshot)
        if retaliation_entries:
            raw_outputs.setdefault("dialogue", []).extend(retaliation_entries)
