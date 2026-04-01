"""Director — central orchestrator of the text quest."""

from __future__ import annotations

import asyncio
import json as _json
from dataclasses import dataclass, field
from typing import Any, NamedTuple

from cast.base_performer_class import BasePerformer
from cast.dice import CombatRoll, roll_aggression, roll_combat
from knowledge.memory import MemoryManager
from knowledge.node import KnowledgeScope
from llm.message import Message, Role
from models.game_state import GameState
from prompts.director_prompts import DIRECTOR_ACTION_ROUTING, DIRECTOR_SYSTEM
from timeline.event import GameEvent
from timeline.event_manager import EventManager
from timeline.time_costs import resolve_time_cost

_SCENE_SUMMARY_CHARS = 500
_KEY_ACTION_TYPE = "action_type"
_KEY_GAME_STATE = "game_state"
_DEFAULT_ACTION = "OTHER"

# Actions that increment the turn counter.
TURN_COUNTING_ACTIONS: frozenset[str] = frozenset(("EXPLORE", "MOVE", "INTERACT", "TALK", "SLEEP"))

# Actions that trigger a scene rebuild (new location, time-of-day shift, etc.).
SCENE_CHANGING_ACTIONS: frozenset[str] = frozenset(("EXPLORE", "MOVE", "SLEEP"))


@dataclass
class DirectorDeps:
    """Runtime dependencies the Director needs to orchestrate the game."""

    game_state: GameState
    event_manager: EventManager
    memory_manager: MemoryManager


@dataclass
class DirectorCast:
    """The ensemble of specialist agents the Director delegates to."""

    scene_builder: Any
    narrator: Any
    npc_generator: Any
    data_miner: Any
    actors: dict[str, Any] = field(default_factory=dict)


class RetaliationWork(NamedTuple):
    """Pre-computed data for a single NPC retaliation."""

    npc: Any
    actor: Any
    retaliation_input: str
    aggression: Any
    combat_roll: CombatRoll


class Director(BasePerformer):
    """Central orchestrator.

    Receives player input, classifies the action, advances game time,
    resolves completed events, delegates to specialist agents, and
    passes everything through the Narrator for final output.
    """

    def __init__(
        self,
        *,
        llm_client: Any,
        deps: DirectorDeps,
        cast: DirectorCast,
        language: str = "English",
    ):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=DIRECTOR_SYSTEM,
        )
        self.game_state = deps.game_state
        self.event_manager = deps.event_manager
        self.memory_manager = deps.memory_manager
        self.scene_builder = cast.scene_builder
        self.narrator = cast.narrator
        self.npc_generator = cast.npc_generator
        self.data_miner = cast.data_miner
        self.actors: dict[str, Any] = dict(cast.actors)
        self._language = language

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def act(self, input_data: str, context: dict | None = None) -> str:
        """Process a player action and return the narrated response.

        This is the main game loop entry-point per turn.
        """
        self._sync_context_from_state()

        routing_plan = await self._route_action(input_data)

        if routing_plan.get("needs_clarification"):
            self._save_pending_clarification(input_data, routing_plan)
            return routing_plan.get(
                "clarification_question",
                "Could you be more specific about what you want to do?",
            )

        self.game_state.pending_clarification = None
        action_type = routing_plan.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION)
        completed_events = self._advance_and_resolve(action_type, routing_plan.get("time_cost_override"))
        narrated_response = await self._execute_plan(routing_plan, input_data, completed_events)

        self._append_turn_logs(input_data, narrated_response, action_type)
        return narrated_response

    def register_actor(self, npc_uuid: str, actor: Any) -> None:
        """Register an Actor agent for an NPC."""
        self.actors[npc_uuid] = actor

    def schedule_event(self, event: GameEvent) -> str:
        """Convenience wrapper to schedule an event."""
        return self.event_manager.schedule(event)

    # ------------------------------------------------------------------
    # Internal: turn bookkeeping
    # ------------------------------------------------------------------

    def _append_turn_logs(self, player_action: str, narrated_response: str, action_type: str) -> None:
        """Update game state conversation logs after a turn."""
        if action_type in TURN_COUNTING_ACTIONS:
            self.game_state.turn_count += 1
        self.game_state.conversation_log.append(
            {
                "turn": self.game_state.turn_count,
                "player_action": player_action,
                "response": narrated_response,
                "game_clock": self.game_state.game_clock,
            }
        )
        self.game_state.scene_conversation_log.append(
            {
                "player_action": player_action,
                "response_summary": narrated_response[:_SCENE_SUMMARY_CHARS],
                _KEY_ACTION_TYPE: action_type,
            }
        )

    # ------------------------------------------------------------------
    # Internal: routing
    # ------------------------------------------------------------------

    async def _route_action(self, player_action: str) -> dict:
        """Use the LLM to classify the action and produce a routing plan.

        If a pending clarification exists in the game state, the player's
        raw answer is sent as a plain follow-up message (NOT wrapped in
        the routing prompt template) so the LLM treats it as a direct
        answer to the prior question rather than a new standalone action.

        For normal (non-clarification) calls, scene conversation history
        is injected so the Director remembers what happened in prior turns
        within the same scene.
        """
        history = self._load_pending_clarification()
        if history:
            # Follow-up to a clarification — prepend scene history so the
            # LLM retains context of what happened earlier in the scene
            # (e.g. an ongoing fight) when resolving the follow-up.
            scene_history = self._build_scene_history() or []
            return await self._send_json(
                player_action,
                conversation=scene_history + history,
            )
        # Normal routing — wrap in the full routing prompt with scene history
        prompt = DIRECTOR_ACTION_ROUTING.render(player_action=player_action)
        return await self._send_json(prompt, conversation=self._build_scene_history())

    def _save_pending_clarification(self, player_action: str, routing_plan: dict) -> None:
        """Persist a clarification exchange in game state (survives restarts)."""
        prompt = DIRECTOR_ACTION_ROUTING.render(player_action=player_action)
        self.game_state.pending_clarification = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": _json.dumps(routing_plan, ensure_ascii=False)},
        ]

    def _load_pending_clarification(self) -> list[Message] | None:
        """Restore pending clarification from game state as Message objects."""
        raw = self.game_state.pending_clarification
        if not raw:
            return None
        return [
            Message(role=Role.USER if msg["role"] == "user" else Role.ASSISTANT, content=msg["content"]) for msg in raw
        ]

    def _build_scene_history(self) -> list[Message] | None:
        """Build a conversation history from the current scene's log.

        Returns ``Message`` pairs (user action + assistant routing response)
        for the last 10 exchanges so the Director LLM maintains context
        across turns within the same scene.
        """
        log = self.game_state.scene_conversation_log
        if not log:
            return None
        messages: list[Message] = []
        for entry in log[-10:]:
            messages.append(
                Message(
                    role=Role.USER,
                    content=f'Player action: "{entry["player_action"]}"',
                )
            )
            messages.append(
                Message(
                    role=Role.ASSISTANT,
                    content=_json.dumps(
                        {
                            _KEY_ACTION_TYPE: entry.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION),
                            "result_summary": entry.get("response_summary", ""),
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        return messages if messages else None

    # ------------------------------------------------------------------
    # Internal: time & events
    # ------------------------------------------------------------------

    def _advance_and_resolve(self, action_type: str, time_override: float | None) -> list[GameEvent]:
        """Advance the game clock and return completed events."""
        hours = resolve_time_cost(action_type, time_override)
        return self.event_manager.advance_time(hours)

    def _partition_events(self, events: list[GameEvent]) -> tuple[list[GameEvent], list[GameEvent]]:
        """Split events into local (visible to player) and remote."""
        player_loc = self.game_state.player.location_id
        local: list[GameEvent] = []
        remote: list[GameEvent] = []
        for ev in events:
            if ev.location_id == player_loc:
                local.append(ev)
            else:
                remote.append(ev)
        return local, remote

    async def _process_remote_events(self, events: list[GameEvent]) -> None:
        """Feed remote events into the memory system as rumours / knowledge."""
        await asyncio.gather(*(self._create_memory_for_event(ev) for ev in events))

    def _build_memory_kwargs(self, ev: GameEvent) -> dict:
        """Build keyword arguments for create_memory_from_event from a GameEvent."""
        scope_map = {
            "local": KnowledgeScope.LOCAL,
            "city": KnowledgeScope.CITY,
            "region": KnowledgeScope.REGION,
            "country": KnowledgeScope.COUNTRY,
            "world": KnowledgeScope.WORLD,
        }
        scope = scope_map.get(ev.scope, KnowledgeScope.LOCAL)
        witnesses: list[str] = []
        if ev.location_id and ev.location_id in self.game_state.locations:
            witnesses = list(self.game_state.locations[ev.location_id].npcs_present)
        return {
            "event_description": ev.on_complete_description or ev.name,
            "witness_ids": witnesses,
            "scope": scope,
            "location_id": ev.location_id,
            "game_time": self.game_state.game_clock,
        }

    async def _create_memory_for_event(self, ev: GameEvent) -> None:
        """Create a memory from a single remote event."""
        await self.memory_manager.create_memory_from_event(**self._build_memory_kwargs(ev))

    # ------------------------------------------------------------------
    # Internal: delegation
    # ------------------------------------------------------------------

    async def _execute_plan(
        self,
        plan: dict,
        player_action: str,
        completed_events: list[GameEvent],
    ) -> str:
        """Delegate to agents based on the routing plan and assemble output."""
        raw_outputs: dict[str, Any] = {}

        local_events = await self._process_events(completed_events, raw_outputs)
        await self._prepare_scene(
            plan.get("delegate_to", []), plan.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION), player_action, raw_outputs
        )
        await self._process_target_npcs(plan, player_action, raw_outputs)

        if local_events:
            raw_outputs["completed_events"] = [ev.on_complete_description or ev.name for ev in local_events]

        return await self.narrator.execute(
            input_data=raw_outputs,
            context={
                "player_action": player_action,
                _KEY_GAME_STATE: self.game_state,
                "scene_history": self.game_state.scene_conversation_log[-5:],
            },
        )

    async def _process_events(
        self,
        completed_events: list[GameEvent],
        raw_outputs: dict[str, Any],
    ) -> list[GameEvent]:
        """Partition events, process remote ones, return local events."""
        local_events, remote_events = self._partition_events(completed_events)
        if remote_events:
            await self._process_remote_events(remote_events)
        return local_events

    async def _process_target_npcs(
        self,
        plan: dict,
        player_action: str,
        raw_outputs: dict[str, Any],
    ) -> None:
        """Ensure targeted NPCs exist in the scene, run interactions if needed."""
        target_names = plan.get("targets", [])
        if target_names:
            self._ensure_targets_in_scene(target_names)
            new_npcs = await self._init_scene_npcs()
            if new_npcs:
                raw_outputs["new_npcs"] = [f"{npc.name} ({npc.occupation})" for npc in new_npcs]

        delegates = plan.get("delegate_to", [])
        action_type = plan.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION)
        if self._targets_match_scene_npcs(target_names) or "actor" in delegates or action_type == "TALK":
            await self._run_npc_interactions(player_action, target_names, bool(plan.get("is_aggressive")), raw_outputs)

    async def _prepare_scene(
        self,
        delegates: list[str],
        action_type: str,
        player_action: str,
        raw_outputs: dict[str, Any],
    ) -> None:
        """Build scene if needed and initialise any uninitialized NPCs."""
        if "scene_builder" in delegates or action_type in SCENE_CHANGING_ACTIONS:
            scene = await self.scene_builder.execute(
                input_data=player_action,
                context={_KEY_GAME_STATE: self.game_state},
            )
            raw_outputs["scene"] = scene
            self.game_state.current_scene = scene
            self.game_state.scene_number += 1
            self.game_state.scene_conversation_log = []

        await self._init_scene_npcs()

    async def _run_npc_interactions(
        self,
        player_action: str,
        target_names: list[str],
        is_aggressive: bool,
        raw_outputs: dict[str, Any],
    ) -> None:
        """Run NPC dialogue and retaliation checks, updating raw_outputs."""
        mood_snapshot = {uuid: npc.current_mood for uuid, npc in self.game_state.npcs.items()}

        dialogue = await self._handle_dialogue(player_action, target_names, is_aggressive=is_aggressive)
        if dialogue:
            raw_outputs["dialogue"] = dialogue

        retaliation = await self._check_retaliation(mood_snapshot)
        if retaliation:
            raw_outputs.setdefault("dialogue", []).extend(retaliation)

    async def _handle_dialogue(
        self,
        player_action: str,
        target_names: list[str],
        is_aggressive: bool = False,
    ) -> list[dict[str, str]]:
        """Route dialogue to the correct Actor agents.

        Matches targets by NPC name **and** by the SceneNPC role
        description, so that both "караульный стражник" (role) and
        "Теодорос" (generated name) resolve correctly.

        When ``is_aggressive`` is True, a combat dice roll is performed
        for each targeted NPC and the outcome is injected into the
        Actor's input so the LLM must narrate that result.
        """
        work_items = self._collect_dialogue_targets(target_names, player_action, is_aggressive)

        return list(
            await asyncio.gather(
                *(
                    self._execute_npc_dialogue(wi_npc, wi_actor, wi_text, wi_roll)
                    for wi_npc, wi_actor, wi_text, wi_roll in work_items
                )
            )
        )

    def _collect_dialogue_targets(
        self,
        target_names: list[str],
        player_action: str,
        is_aggressive: bool,
    ) -> list[tuple[Any, Any, str, CombatRoll | None]]:
        """Match target names to NPCs and prepare dialogue work items."""
        matched_uuids = self._resolve_target_uuids(target_names)
        return [
            (
                self.game_state.npcs[uid],
                self.actors[uid],
                *self._build_combat_action(
                    player_action,
                    self.game_state.npcs[uid],
                    is_aggressive,
                ),
            )
            for uid in matched_uuids
            if uid in self.actors
        ]

    def _resolve_target_uuids(self, target_names: list[str]) -> list[str]:
        """Resolve target names to a de-duplicated list of NPC UUIDs."""
        targets_lower = {target.lower() for target in target_names}
        candidate_uuids = self._role_matched_uuids(targets_lower) | {
            uid for uid, npc in self.game_state.npcs.items() if npc.name.lower() in targets_lower
        }
        return self._deduplicate_by_name(candidate_uuids)

    def _deduplicate_by_name(self, uuids: set[str]) -> list[str]:
        """De-duplicate NPC UUIDs so each name appears only once."""
        seen: set[str] = set()
        unique_uuids: list[str] = []
        for uid in uuids:
            npc = self.game_state.npcs.get(uid)
            if npc and npc.name.lower() not in seen:
                seen.add(npc.name.lower())
                unique_uuids.append(uid)
        return unique_uuids

    def _role_matched_uuids(self, targets_lower: set[str]) -> set[str]:
        """Return UUIDs of scene NPCs whose role matches a target name."""
        scene = self.game_state.current_scene
        if not scene:
            return set()
        return {snpc.uuid for snpc in scene.npcs_present if snpc.uuid and snpc.role.lower() in targets_lower}

    def _build_combat_action(
        self,
        player_action: str,
        npc: Any,
        is_aggressive: bool,
    ) -> tuple[str, CombatRoll | None]:
        """Build action text and optional combat roll for an NPC interaction."""
        if not is_aggressive:
            return player_action, None
        combat_roll = roll_combat(npc.get_attribute("combat_skill", 3))
        action_text = (
            f"{player_action}\n\n"
            f"[DICE ROLL: player {combat_roll.player_roll} vs "
            f"NPC {combat_roll.npc_roll}+{combat_roll.npc_bonus}]\n"
            f"OUTCOME: {combat_roll.description}\n"
            f"You MUST narrate this outcome. Do NOT override the dice result."
        )
        return action_text, combat_roll

    async def _execute_npc_dialogue(
        self,
        npc: Any,
        actor: Any,
        action_text: str,
        combat_roll: CombatRoll | None,
    ) -> dict[str, str]:
        """Execute a single NPC dialogue and return the result entry."""
        response = await actor.execute(
            input_data=action_text,
            context={
                "npc": npc,
                _KEY_GAME_STATE: self.game_state,
                "location_name": self._get_location_name(npc.location_id),
            },
        )
        result_entry: dict[str, str] = {
            "npc_name": npc.name,
            "response": response,
        }
        if combat_roll:
            player = combat_roll.player_roll
            npc_total = "{0}+{1}".format(combat_roll.npc_roll, combat_roll.npc_bonus)
            outcome = combat_roll.outcome.value
            result_entry["combat_roll"] = "d20: player {0} vs NPC {1} → {2}".format(
                player,
                npc_total,
                outcome,
            )
        return result_entry

    async def _init_scene_npcs(self) -> list[Any]:
        """Initialise any ``SceneNPC`` objects that haven't been turned into
        full ``NPCCard`` + ``Actor`` instances yet.

        This runs unconditionally on every turn so that NPC availability
        never depends on the LLM's routing decision.

        Returns the list of newly created ``NPCCard`` objects (empty when
        nothing needed initialisation).
        """
        scene = self.game_state.current_scene
        if not scene:
            return []
        uninit = [snpc for snpc in scene.npcs_present if snpc.need_init]
        if not uninit:
            return []
        new_cards = await self.npc_generator.execute(
            input_data=[snpc.role for snpc in uninit],
            context={_KEY_GAME_STATE: self.game_state},
        )
        for scene_npc, card in zip(uninit, new_cards):
            self._register_new_npc(card)
            scene_npc.uuid = card.uuid
        return list(new_cards)

    def _targets_match_scene_npcs(self, target_names: list[str]) -> bool:
        """Return ``True`` if any target name matches an initialised SceneNPC."""
        scene = self.game_state.current_scene
        if not scene or not target_names:
            return False
        targets_lower = {target.lower() for target in target_names}
        for snpc in scene.npcs_present:
            if not snpc.uuid or snpc.uuid not in self.game_state.npcs:
                continue
            npc = self.game_state.npcs[snpc.uuid]
            # Match by role description or by generated NPC name
            if snpc.role.lower() in targets_lower or npc.name.lower() in targets_lower:
                return True
        return False

    def _ensure_targets_in_scene(self, target_names: list[str]) -> None:
        """Make sure that every target the Director identified is represented
        as a ``SceneNPC`` in the current scene.  If a target matches an
        existing ``SceneNPC`` by role, nothing happens.  Otherwise a new
        ``SceneNPC`` is appended (with ``need_init=True``).
        """
        from models.scene import SceneNPC

        scene = self.game_state.current_scene
        if not scene:
            return
        existing_roles = {snpc.role.lower() for snpc in scene.npcs_present}
        # Also check already-initialised NPC names
        npcs = self.game_state.npcs
        existing_names = {
            npcs[snpc.uuid].name.lower() for snpc in scene.npcs_present if snpc.uuid and snpc.uuid in npcs
        }
        for target in target_names:
            if target.lower() not in existing_roles and target.lower() not in existing_names:
                scene.npcs_present.append(SceneNPC(role=target))

    def _register_new_npc(self, npc: Any) -> None:
        """Register a new NPC in the game state and create an Actor for it."""
        from cast.actor import Actor
        from knowledge.query import KnowledgeQueryEngine

        self.game_state.npcs[npc.uuid] = npc

        # Add to location
        if npc.location_id and npc.location_id in self.game_state.locations:
            self.game_state.locations[npc.location_id].add_npc(npc.uuid)

        # Create an Actor for dialogue
        actor = Actor(
            llm_client=self.llm_client,
            npc=npc,
            knowledge_query=KnowledgeQueryEngine(self.game_state.knowledge_graph),
        )
        actor.set_context(language=self._language)
        self.register_actor(npc.uuid, actor)

    # ------------------------------------------------------------------
    # Internal: NPC retaliation
    # ------------------------------------------------------------------

    async def _check_retaliation(
        self,
        mood_snapshot: dict[str, str],
    ) -> list[dict[str, str]]:
        """After dialogue, check if any NPC whose mood changed wants to
        attack the player.

        Rolls 1d20 against a mood-based threshold (e.g. hostile=5+).
        If the roll passes, the NPC retaliates — a combat dice roll is
        performed and injected into a second Actor call.
        """
        retaliated_names: set[str] = set()
        work_items: list[RetaliationWork] = []
        for npc_uuid, actor in self.actors.items():
            work = self._build_retaliation_work(npc_uuid, actor, mood_snapshot, retaliated_names)
            if work is not None:
                work_items.append(work)

        return list(await asyncio.gather(*(self._execute_retaliation(wi) for wi in work_items)))

    def _build_retaliation_work(
        self,
        npc_uuid: str,
        actor: Any,
        mood_snapshot: dict[str, str],
        retaliated_names: set[str],
    ) -> RetaliationWork | None:
        """Check if an NPC should retaliate and build work item if so."""
        npc = self.game_state.npcs.get(npc_uuid)
        if not npc or npc.name.lower() in retaliated_names:
            return None
        if npc.current_mood == mood_snapshot.get(npc_uuid, "neutral"):
            return None

        aggression = roll_aggression(npc.current_mood)
        if aggression is None or not aggression.will_attack:
            return None
        retaliated_names.add(npc.name.lower())

        combat_roll = roll_combat(npc.get_attribute("combat_skill", 3))
        retaliation_input = (
            f"{npc.name} retaliates against the player!\n\n"
            f"[DICE ROLL: player {combat_roll.player_roll} vs "
            f"NPC {combat_roll.npc_roll}+{combat_roll.npc_bonus}]\n"
            f"OUTCOME: {combat_roll.description}\n"
            f"You MUST narrate this outcome. The NPC attacks FIRST — "
            f"they are the aggressor now. Do NOT override the dice result."
        )
        return RetaliationWork(npc, actor, retaliation_input, aggression, combat_roll)

    async def _execute_retaliation(self, work: RetaliationWork) -> dict[str, str]:
        """Execute a single NPC retaliation and return the result entry."""
        response = await work.actor.execute(
            input_data=work.retaliation_input,
            context={
                "npc": work.npc,
                _KEY_GAME_STATE: self.game_state,
                "location_name": self._get_location_name(work.npc.location_id),
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

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    def _sync_context_from_state(self) -> None:
        """Update system prompt variables from the current game state."""
        scene = self.game_state.current_scene

        context_vars = dict(
            setting_name=self.game_state.setting.name,
            time_period=self.game_state.setting.time_period,
            scene_description=(scene.description if scene else "No scene set yet"),
            npcs_present=self._format_npcs_present(scene),
            points_of_interest=self._format_pois(scene),
            game_time=self.game_state.game_time,
            game_clock=str(round(self.game_state.game_clock, 1)),
        )

        history_summary = self._format_scene_history()
        if history_summary:
            context_vars["scene_history_summary"] = history_summary

        self.set_context(**context_vars)

    def _format_npcs_present(self, scene: Any) -> str:
        """Format NPC names for the system prompt."""
        if not scene:
            return "None"
        return (
            ", ".join(
                self.game_state.npcs[snpc.uuid].name
                for snpc in scene.npcs_present
                if snpc.uuid and snpc.uuid in self.game_state.npcs
            )
            or "None"
        )

    def _format_pois(self, scene: Any) -> str:
        """Format points of interest for the system prompt."""
        if scene and scene.points_of_interest:
            return ", ".join(scene.points_of_interest)
        return "None"

    def _format_scene_history(self) -> str | None:
        """Format recent scene actions for the system prompt."""
        scene_log = self.game_state.scene_conversation_log
        if not scene_log:
            return None
        return "\n".join(
            f"- Player: {entry['player_action']} -> {entry.get('action_type', '?')}" for entry in scene_log[-5:]
        )

    def _get_location_name(self, location_id: str | None) -> str:
        if location_id and location_id in self.game_state.locations:
            return self.game_state.locations[location_id].name
        return "this place"
