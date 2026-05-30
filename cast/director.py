"""Director — central orchestrator of the text quest engine."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from cast.base_performer_class import BasePerformer
from cast import director_context, director_dialogue, director_events
from cast import director_execution, director_retaliation, director_routing
from cast.director_tools import RouteResult
from cast.known_npcs import mark_player_text_introductions
from cast import npc_background_tick
from cast.npc_ticker import NPCTicker
from cast.npc_turn import NPCTurnResolver
from cast.schemas.action_plan import ClarificationRequest, WaitPlan
from cast.wait_detection import build_forced_wait_plan, detect_wait_intent, is_incapacitated
from knowledge import memory as memory_mod
from llm.turn_event_logger import record_turn_event
from models import game_state as gs_mod
from prompts.director_prompts import get_director_prompts
from timeline import event as event_mod, event_manager as event_manager_mod

_DEFAULT_CLARIFICATION = "Could you be more specific about what you want to do?"


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
        game_state: gs_mod.GameState,
        event_manager: event_manager_mod.EventManager,
        memory_manager: memory_mod.MemoryManager,
        scene_builder: Any,
        narrator: Any,
        npc_generator: Any,
        data_miner: Any,
        item_generator: Any,
        world_chronicler: Any | None = None,
        dramaturge: Any | None = None,
        actors: dict[UUID, Any] | None = None,
        language: str = "English",
    ):
        prompts = get_director_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=prompts.system,
        )
        self._game_state = game_state
        self._event_manager = event_manager
        self._actors: dict[UUID, Any] = dict(actors or {})
        self._language = language
        self.set_context(language=language)

        self._ctx = director_context.ContextFormatter(game_state)
        self._router = director_routing.ActionRouter(
            game_state,
            self._send_tool,
            prompts.action_routing,
        )
        self._events = director_events.EventProcessor(game_state, event_manager, memory_manager)
        self._dialogue = director_dialogue.DialogueHandler(game_state, self._actors, memory_manager)
        self._retaliation = director_retaliation.RetaliationHandler(game_state, self._actors)
        self._npc_turns = NPCTurnResolver(game_state, self._actors)
        self._background_ticker = npc_background_tick.NPCBackgroundTicker(game_state, memory_manager)
        self._npc_ticker = NPCTicker(game_state)
        self._executor = director_execution.PlanExecutor(
            game_state=game_state,
            events=self._events,
            event_manager=event_manager,
            dialogue=self._dialogue,
            retaliation=self._retaliation,
            npc_turns=self._npc_turns,
            npc_ticker=self._npc_ticker,
            memory_manager=memory_manager,
            scene_builder=scene_builder,
            narrator=narrator,
            npc_generator=npc_generator,
            data_miner=data_miner,
            item_generator=item_generator,
            world_chronicler=world_chronicler,
            dramaturge=dramaturge,
            register_npc_fn=self._register_new_npc,
        )
        self._narrator = narrator

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def act(self, input_data: str, context: dict | None = None) -> str:
        """Process a player action and return the narrated response."""
        self._ctx.sync_context(self)

        forced_wait = self._check_forced_wait(input_data)
        plan: RouteResult = await self._router.route_action(input_data) if forced_wait is None else forced_wait

        if isinstance(plan, ClarificationRequest):
            self._router.save_pending_clarification(input_data, plan)
            return plan.question or _DEFAULT_CLARIFICATION

        self._game_state.pending_clarification = None
        mark_player_text_introductions(input_data, self._game_state)
        action_type = plan.action_type
        completed = await self._advance_clock_and_tick_background(action_type, plan.time_cost_override)
        narrated = await self._executor.execute_plan(plan, input_data, completed)

        self._ctx.append_turn_logs(input_data, narrated, action_type)
        return narrated

    def register_actor(self, npc_uuid: UUID, actor: Any) -> None:
        """Register an Actor agent for an NPC."""
        self._actors[npc_uuid] = actor

    def schedule_event(self, event: event_mod.GameEvent) -> UUID:
        """Convenience wrapper to schedule an event."""
        return self._event_manager.schedule(event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _advance_clock_and_tick_background(
        self,
        action_type: str,
        time_override: float | None,
    ) -> list[event_mod.GameEvent]:
        """Advance the clock, run the off-scene NPC goal tick, and return completed events."""
        clock_before = self._game_state.game_clock
        completed, hours_advanced = self._events.advance_and_resolve(action_type, time_override)
        record_turn_event(
            "clock_advance",
            {
                "action_type": action_type,
                "hours": hours_advanced,
                "clock_before": clock_before,
                "clock_after": self._game_state.game_clock,
                "completed_events": [event.name for event in completed],
            },
            agent_name="Director",
        )
        await self._background_ticker.tick(hours_advanced)
        return completed

    def _check_forced_wait(self, input_data: str) -> WaitPlan | None:
        """Short-circuit to WAIT if player is incapacitated or typed a wait keyword."""
        player_status = self._game_state.player.physical_status
        if is_incapacitated(player_status):
            return build_forced_wait_plan(player_status)
        if detect_wait_intent(input_data, self._language):
            return build_forced_wait_plan("voluntary")
        return None

    def _register_new_npc(self, npc: Any) -> None:
        """Register a new NPC in the game state and create an Actor."""
        from cast.actor import Actor
        from knowledge.query import KnowledgeQueryEngine

        self._game_state.npcs[npc.uuid] = npc

        locations = self._game_state.locations
        if npc.location_id and npc.location_id in locations:
            locations[npc.location_id].add_npc(npc.uuid)

        # Register the NPC as a graph node so MemoryManager.summarize_interaction
        # can attach WITNESSED edges from the NPC to personal-memory nodes.
        self._game_state.knowledge_graph.register_actor_node(
            npc.uuid,
            label="{0} ({1})".format(npc.name, npc.occupation),
        )

        actor = Actor(
            llm_client=self.llm_client,
            npc=npc,
            knowledge_query=KnowledgeQueryEngine(self._game_state.knowledge_graph),
            language=self._language,
        )
        self.register_actor(npc.uuid, actor)
