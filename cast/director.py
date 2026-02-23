"""Director — central orchestrator of the text quest."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from knowledge.memory import MemoryManager
from knowledge.node import KnowledgeScope
from models.game_state import GameState
from prompts.director_prompts import DIRECTOR_ACTION_ROUTING, DIRECTOR_SYSTEM
from timeline.event import GameEvent
from timeline.event_manager import EventManager
from timeline.time_costs import resolve_time_cost


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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def act(self, input_data: str, context: dict | None = None) -> str:
        """Process a player action and return the narrated response.

        This is the main game loop entry-point per turn.
        """
        # 1. Update system prompt from current game state
        self._sync_context_from_state()

        # 2. Route the action — LLM classifies + produces a plan
        routing_plan = await self._route_action(input_data)

        # 3. If clarification needed, return question
        if routing_plan.get("needs_clarification"):
            return routing_plan.get(
                "clarification_question",
                "Could you be more specific about what you want to do?",
            )

        # 4. Advance time and resolve events
        action_type = routing_plan.get("action_type", "OTHER")
        time_override = routing_plan.get("time_cost_override")
        completed_events = self._advance_and_resolve(action_type, time_override)

        # 5. Execute the plan by delegating to agents
        result = await self._execute_plan(routing_plan, input_data, completed_events)

        # 6. Update game state bookkeeping
        self.game_state.turn_count += 1
        self.game_state.conversation_log.append({
            "turn": self.game_state.turn_count,
            "player_action": input_data,
            "response": result,
            "game_clock": self.game_state.game_clock,
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
        """Use the LLM to classify the action and produce a routing plan."""
        prompt = DIRECTOR_ACTION_ROUTING.render(player_action=player_action)
        return await self._send_json(prompt)

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
        if "scene_builder" in delegates or action_type in ("EXPLORE", "MOVE"):
            scene = await self.scene_builder.act(
                input_data=player_action,
                context={"game_state": self.game_state},
            )
            raw_outputs["scene"] = scene
            self.game_state.current_scene = scene

            # Auto-generate NPCs mentioned in the scene
            if scene.npcs_present:
                await self._ensure_npcs_exist(scene.npcs_present)

        # --- Dialogue ---
        if "actor" in delegates or action_type == "TALK":
            target_names = plan.get("targets", [])
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
            },
        )
        return narrated

    async def _handle_dialogue(
        self, player_action: str, target_names: list[str]
    ) -> list[dict[str, str]]:
        """Route dialogue to the correct Actor agents."""
        results: list[dict[str, str]] = []
        for npc_uuid, actor in self.actors.items():
            npc = self.game_state.npcs.get(npc_uuid)
            if npc and npc.name.lower() in [t.lower() for t in target_names]:
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

    async def _ensure_npcs_exist(self, npc_names_or_roles: list[str]) -> None:
        """If the scene mentions NPCs that don't exist yet, generate them."""
        existing_names = {
            npc.name.lower() for npc in self.game_state.npcs.values()
        }
        missing = [
            name
            for name in npc_names_or_roles
            if name.lower() not in existing_names
        ]
        if missing:
            new_npcs = await self.npc_generator.act(
                input_data=missing,
                context={"game_state": self.game_state},
            )
            for npc in new_npcs:
                self._register_new_npc(npc)

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
        self.register_actor(npc.uuid, actor)

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    def _sync_context_from_state(self) -> None:
        """Update system prompt variables from the current game state."""
        scene = self.game_state.current_scene
        npc_names = (
            ", ".join(
                self.game_state.npcs[uid].name
                for uid in (scene.npcs_present if scene else [])
                if uid in self.game_state.npcs
            )
            or "None"
        )
        pois = (
            ", ".join(scene.points_of_interest)
            if scene and scene.points_of_interest
            else "None"
        )

        self.set_context(
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

    def _get_location_name(self, location_id: str | None) -> str:
        if location_id and location_id in self.game_state.locations:
            return self.game_state.locations[location_id].name
        return "this place"
