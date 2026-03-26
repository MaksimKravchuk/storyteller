"""Director — central orchestrator of the text quest."""

from __future__ import annotations

import json as _json
from typing import Any

from cast.base_performer_class import BasePerformer
from knowledge.memory import MemoryManager
from knowledge.node import KnowledgeScope
from llm.message import Message, Role
from models.game_state import GameState
from prompts.director_prompts import DIRECTOR_ACTION_ROUTING, DIRECTOR_SYSTEM
from timeline.event import GameEvent
from timeline.event_manager import EventManager
from timeline.time_costs import resolve_time_cost

# Actions that increment the turn counter.
TURN_COUNTING_ACTIONS = {"EXPLORE", "MOVE", "INTERACT", "TALK", "SLEEP"}

# Actions that trigger a scene rebuild (new location, time-of-day shift, etc.).
SCENE_CHANGING_ACTIONS = {"EXPLORE", "MOVE", "SLEEP"}


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
        game_state: GameState,
        event_manager: EventManager,
        memory_manager: MemoryManager,
        scene_builder: Any,  # SceneBuilder (forward ref avoids circular import)
        narrator: Any,       # Narrator
        npc_generator: Any,  # NPCGenerator
        data_miner: Any,     # DataMiner
        actors: dict[str, Any] | None = None,  # NPC UUID -> Actor
        language: str = "English",
    ):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=DIRECTOR_SYSTEM,
        )
        self.game_state = game_state
        self.event_manager = event_manager
        self.memory_manager = memory_manager
        self.scene_builder = scene_builder
        self.narrator = narrator
        self.npc_generator = npc_generator
        self.data_miner = data_miner
        self.actors: dict[str, Any] = actors or {}  # NPC UUID -> Actor
        self._language = language

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def act(self, input_data: str, context: dict | None = None) -> str:
        """Process a player action and return the narrated response.

        This is the main game loop entry-point per turn.
        """
        # 1. Update system prompt from current game state
        self._sync_context_from_state()

        # 2. Route the action — LLM classifies + produces a plan.
        #    Pass pending clarification context so the model can resolve
        #    follow-up replies like "да" or "1".
        routing_plan = await self._route_action(input_data)

        # 3. If clarification needed, persist the exchange and return
        if routing_plan.get("needs_clarification"):
            question = routing_plan.get(
                "clarification_question",
                "Could you be more specific about what you want to do?",
            )
            # Persist exchange in game state (survives engine recreation)
            self._save_pending_clarification(input_data, routing_plan)
            return question

        # Successful routing — clear pending clarification
        self.game_state.pending_clarification = None

        # 4. Advance time and resolve events
        action_type = routing_plan.get("action_type", "OTHER")
        time_override = routing_plan.get("time_cost_override")
        completed_events = self._advance_and_resolve(action_type, time_override)

        # 5. Execute the plan by delegating to agents
        result = await self._execute_plan(routing_plan, input_data, completed_events)

        # 6. Update game state bookkeeping
        if action_type in TURN_COUNTING_ACTIONS:
            self.game_state.turn_count += 1
        self.game_state.conversation_log.append({
            "turn": self.game_state.turn_count,
            "player_action": input_data,
            "response": result,
            "game_clock": self.game_state.game_clock,
        })
        self.game_state.scene_conversation_log.append({
            "player_action": input_data,
            "response_summary": result[:500],
            "action_type": action_type,
        })

        return result

    def register_actor(self, npc_uuid: str, actor: Any) -> None:
        """Register an Actor agent for an NPC."""
        self.actors[npc_uuid] = actor

    def schedule_event(self, event: GameEvent) -> str:
        """Convenience wrapper to schedule an event."""
        return self.event_manager.schedule(event)

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

    def _save_pending_clarification(
        self, player_action: str, routing_plan: dict
    ) -> None:
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
            Message(role=Role.USER if m["role"] == "user" else Role.ASSISTANT, content=m["content"])
            for m in raw
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
            messages.append(Message(
                role=Role.USER,
                content=f'Player action: "{entry["player_action"]}"',
            ))
            messages.append(Message(
                role=Role.ASSISTANT,
                content=_json.dumps({
                    "action_type": entry.get("action_type", "OTHER"),
                    "result_summary": entry.get("response_summary", ""),
                }, ensure_ascii=False),
            ))
        return messages if messages else None

    # ------------------------------------------------------------------
    # Internal: time & events
    # ------------------------------------------------------------------

    def _advance_and_resolve(
        self, action_type: str, time_override: float | None
    ) -> list[GameEvent]:
        """Advance the game clock and return completed events."""
        hours = resolve_time_cost(action_type, time_override)
        return self.event_manager.advance_time(hours)

    def _partition_events(
        self, events: list[GameEvent]
    ) -> tuple[list[GameEvent], list[GameEvent]]:
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
        for ev in events:
            scope_map = {
                "local": KnowledgeScope.LOCAL,
                "city": KnowledgeScope.CITY,
                "region": KnowledgeScope.REGION,
                "country": KnowledgeScope.COUNTRY,
                "world": KnowledgeScope.WORLD,
            }
            scope = scope_map.get(ev.scope, KnowledgeScope.LOCAL)

            # Find NPCs at the event location to be witnesses
            witnesses: list[str] = []
            if ev.location_id and ev.location_id in self.game_state.locations:
                witnesses = list(
                    self.game_state.locations[ev.location_id].npcs_present
                )

            await self.memory_manager.create_memory_from_event(
                event_description=ev.on_complete_description or ev.name,
                witness_ids=witnesses,
                scope=scope,
                location_id=ev.location_id,
                game_time=self.game_state.game_clock,
            )

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
        action_type = plan.get("action_type", "OTHER")
        delegates = plan.get("delegate_to", [])
        raw_outputs: dict[str, Any] = {}

        # Partition completed events
        local_events, remote_events = self._partition_events(completed_events)
        if remote_events:
            await self._process_remote_events(remote_events)

        # --- Scene building ---
        if "scene_builder" in delegates or action_type in SCENE_CHANGING_ACTIONS:
            scene = await self.scene_builder.act(
                input_data=player_action,
                context={"game_state": self.game_state},
            )
            raw_outputs["scene"] = scene
            self.game_state.current_scene = scene
            self.game_state.scene_number += 1
            self.game_state.scene_conversation_log = []

        # --- Always initialise any uninitialized scene NPCs ---
        await self._init_scene_npcs()

        # --- Ensure targeted NPCs are in the scene ---
        target_names = plan.get("targets", [])
        if target_names:
            self._ensure_targets_in_scene(target_names)
            # Init any newly added SceneNPCs
            await self._init_scene_npcs()

        # --- Actor / NPC interaction ---
        # Deterministic: if any targets resolve to initialised NPCs in the
        # scene, always invoke their Actors — don't rely on the LLM to
        # include "actor" in delegate_to.
        has_npc_targets = self._targets_match_scene_npcs(target_names)
        if has_npc_targets or "actor" in delegates or action_type == "TALK":
            dialogue = await self._handle_dialogue(player_action, target_names)
            if dialogue:
                raw_outputs["dialogue"] = dialogue

        # --- NPC generation (explicit request) ---
        if "npc_generator" in delegates:
            targets = plan.get("targets", [])
            if targets:
                new_npcs = await self.npc_generator.act(
                    input_data=targets,
                    context={"game_state": self.game_state},
                )
                for npc in new_npcs:
                    self._register_new_npc(npc)
                raw_outputs["new_npcs"] = [
                    f"{npc.name} ({npc.occupation})" for npc in new_npcs
                ]

        # --- Add local events to narrator context ---
        if local_events:
            raw_outputs["completed_events"] = [
                ev.on_complete_description or ev.name for ev in local_events
            ]

        # --- Always pass through Narrator ---
        narrated = await self.narrator.act(
            input_data=raw_outputs,
            context={
                "player_action": player_action,
                "game_state": self.game_state,
                "scene_history": self.game_state.scene_conversation_log[-5:],
            },
        )
        return narrated

    async def _handle_dialogue(
        self, player_action: str, target_names: list[str]
    ) -> list[dict[str, str]]:
        """Route dialogue to the correct Actor agents.

        Matches targets by NPC name **and** by the SceneNPC role
        description, so that both "караульный стражник" (role) and
        "Теодорос" (generated name) resolve correctly.
        """
        targets_lower = {t.lower() for t in target_names}

        # Build a set of NPC UUIDs whose role also matches a target
        scene = self.game_state.current_scene
        role_matched_uuids: set[str] = set()
        if scene:
            for snpc in scene.npcs_present:
                if snpc.uuid and snpc.role.lower() in targets_lower:
                    role_matched_uuids.add(snpc.uuid)

        results: list[dict[str, str]] = []
        for npc_uuid, actor in self.actors.items():
            npc = self.game_state.npcs.get(npc_uuid)
            if not npc:
                continue
            matched = (
                npc.name.lower() in targets_lower
                or npc_uuid in role_matched_uuids
            )
            if matched:
                response = await actor.act(
                    input_data=player_action,
                    context={
                        "npc": npc,
                        "game_state": self.game_state,
                        "location_name": self._get_location_name(npc.location_id),
                    },
                )
                results.append({"npc_name": npc.name, "response": response})
        return results

    async def _init_scene_npcs(self) -> None:
        """Initialise any ``SceneNPC`` objects that haven't been turned into
        full ``NPCCard`` + ``Actor`` instances yet.

        This runs unconditionally on every turn so that NPC availability
        never depends on the LLM's routing decision.
        """
        from models.scene import SceneNPC  # noqa: F811 (re-import for clarity)

        scene = self.game_state.current_scene
        if not scene:
            return
        uninit = [snpc for snpc in scene.npcs_present if snpc.need_init]
        if not uninit:
            return
        roles = [snpc.role for snpc in uninit]
        new_cards = await self.npc_generator.act(
            input_data=roles,
            context={"game_state": self.game_state},
        )
        for scene_npc, card in zip(uninit, new_cards):
            self._register_new_npc(card)
            scene_npc.uuid = card.uuid

    def _targets_match_scene_npcs(self, target_names: list[str]) -> bool:
        """Return ``True`` if any target name matches an initialised SceneNPC."""
        scene = self.game_state.current_scene
        if not scene or not target_names:
            return False
        targets_lower = {t.lower() for t in target_names}
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
        existing_names = {
            self.game_state.npcs[snpc.uuid].name.lower()
            for snpc in scene.npcs_present
            if snpc.uuid and snpc.uuid in self.game_state.npcs
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
    # Internal: helpers
    # ------------------------------------------------------------------

    def _sync_context_from_state(self) -> None:
        """Update system prompt variables from the current game state."""
        scene = self.game_state.current_scene
        npc_names = (
            ", ".join(
                self.game_state.npcs[snpc.uuid].name
                for snpc in (scene.npcs_present if scene else [])
                if snpc.uuid and snpc.uuid in self.game_state.npcs
            )
            or "None"
        )
        pois = (
            ", ".join(scene.points_of_interest)
            if scene and scene.points_of_interest
            else "None"
        )

        context_vars = dict(
            setting_name=self.game_state.setting.name,
            time_period=self.game_state.setting.time_period,
            scene_description=(
                scene.description if scene else "No scene set yet"
            ),
            npcs_present=npc_names,
            points_of_interest=pois,
            game_time=self.game_state.game_time,
            game_clock=str(round(self.game_state.game_clock, 1)),
        )

        # Compact summary of recent scene actions for the system prompt.
        # The section is silently skipped by PromptTemplate when this var
        # is absent (first turn of a scene).
        scene_log = self.game_state.scene_conversation_log
        if scene_log:
            lines = []
            for entry in scene_log[-5:]:
                lines.append(
                    f"- Player: {entry['player_action']} -> {entry.get('action_type', '?')}"
                )
            context_vars["scene_history_summary"] = "\n".join(lines)

        self.set_context(**context_vars)

    def _get_location_name(self, location_id: str | None) -> str:
        if location_id and location_id in self.game_state.locations:
            return self.game_state.locations[location_id].name
        return "this place"
