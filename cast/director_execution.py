"""Plan execution helpers for Director."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from cast.director_dialogue import DialogueHandler
from cast.director_events import EventProcessor
from cast.director_retaliation import RetaliationHandler
from models.game_state import GameState
from timeline.event import GameEvent

_KEY_PLAYER_ACTION = "player_action"
_KEY_ACTION_TYPE = "action_type"
_KEY_GAME_STATE = "game_state"
_DEFAULT_ACTION = "OTHER"

_SCENE_DESC_PREVIEW = 200

# Actions that trigger a scene rebuild.
SCENE_CHANGING_ACTIONS: frozenset[str] = frozenset(("EXPLORE", "MOVE", "SLEEP"))


def _snapshot_moods(npcs: dict) -> dict[str, str]:
    """Capture current mood of every NPC by UUID."""
    return {uuid: npc.current_mood for uuid, npc in npcs.items()}


def _filter_item_targets(targets: list[str], npcs: dict) -> list[str]:
    """Return targets that are NOT NPC names (i.e. likely items/objects)."""
    npc_names_lower = {npc.name.lower() for npc in npcs.values()}
    return [target for target in targets if target.lower() not in npc_names_lower]


@dataclass
class _Agents:
    """Bundle of sub-agents used by PlanExecutor."""

    events: EventProcessor
    dialogue: DialogueHandler
    retaliation: RetaliationHandler


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

        local_events = await self._process_events(completed_events)
        await self._prepare_scene(
            plan.get("delegate_to", []),
            plan.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION),
            player_action,
            raw_outputs,
        )
        await self._process_target_npcs(plan, player_action, raw_outputs)

        if plan.get(_KEY_ACTION_TYPE) == "EXAMINE":
            item_desc = await self._examine_items(plan.get("targets", []), player_action)
            if item_desc:
                raw_outputs["item_examination"] = item_desc

        if local_events:
            raw_outputs["completed_events"] = [ev.on_complete_description or ev.name for ev in local_events]

        return await self._cast.narrator.execute(
            input_data=raw_outputs,
            context={
                _KEY_PLAYER_ACTION: player_action,
                _KEY_GAME_STATE: self._gs,
                "scene_history": self._gs.scene_conversation_log[-5:],
            },
        )

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
            dlg.ensure_targets_in_scene(target_names)
            new_npcs = await dlg.init_scene_npcs(
                self._cast.npc_generator,
                self._register_npc,
                self._cast.item_generator,
            )
            if new_npcs:
                raw_outputs["new_npcs"] = ["{0} ({1})".format(npc.name, npc.occupation) for npc in new_npcs]

        action_type = plan.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION)
        should_talk = dlg.targets_match_scene_npcs(target_names) or "actor" in plan.get("delegate_to", [])
        if should_talk or action_type == "TALK":
            await self._run_interactions(player_action, target_names, bool(plan.get("is_aggressive")), raw_outputs)

    async def _prepare_scene(
        self,
        delegates: list[str],
        action_type: str,
        player_action: str,
        raw_outputs: dict[str, Any],
    ) -> None:
        """Build scene if needed and initialise any uninitialised NPCs."""
        if "scene_builder" in delegates or action_type in SCENE_CHANGING_ACTIONS:
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
    ) -> None:
        """Run NPC dialogue and retaliation checks."""
        mood_snapshot = _snapshot_moods(self._gs.npcs)

        dlg = self._agents.dialogue
        dialogue_entries = await dlg.handle_dialogue(player_action, target_names, is_aggressive=is_aggressive)
        if dialogue_entries:
            raw_outputs["dialogue"] = dialogue_entries

        retaliation_entries = await self._agents.retaliation.check_retaliation(mood_snapshot)
        if retaliation_entries:
            raw_outputs.setdefault("dialogue", []).extend(retaliation_entries)
