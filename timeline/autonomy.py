"""NPC Autonomy — decides what NPCs do when game time advances."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from timeline.dice import (
    CheckType,
    DiceOutcome,
    npc_skill_check,
    DC_EASY,
    DC_MODERATE,
    DC_HARD,
)
from timeline.event import EventEffect, GameEvent

if TYPE_CHECKING:
    from knowledge.memory import MemoryManager
    from llm.base_client import BaseLLMClient
    from models.game_state import GameState
    from models.npc_card import NPCCard


class NPCActionType(Enum):
    """Possible autonomous NPC actions."""

    IDLE = "idle"
    PURSUE_GOAL = "pursue_goal"
    SOCIALIZE = "socialize"
    PATROL = "patrol"
    TRADE = "trade"
    SCHEME = "scheme"
    TRAVEL = "travel"
    REST = "rest"


@dataclass
class AutonomyDecision:
    """Result of deciding what an NPC does."""

    npc_id: str
    npc_name: str
    action_type: NPCActionType
    description: str
    check_type: CheckType | None = None
    difficulty_class: int = DC_MODERATE
    dice_outcome: DiceOutcome | None = None
    resulting_events: list[GameEvent] = field(default_factory=list)


class AutonomyManager:
    """Manages NPC autonomous behavior during time advances.

    Cost management strategy:
      - Tier 1 (LLM): NPCs with importance >= 7 AND (near player OR have active goals)
        -- use LLM to decide their actions (max ~3 NPCs per tick)
      - Tier 2 (Rules): NPCs with importance >= 4
        -- use simple goal-matching rules + dice rolls
      - Tier 3 (Skip): NPCs with importance < 4
        -- do nothing (background characters)
    """

    TIER1_IMPORTANCE = 7
    TIER2_IMPORTANCE = 4

    def __init__(
        self,
        game_state: GameState,
        llm_client: BaseLLMClient,
        memory_manager: MemoryManager,
    ):
        self._game_state = game_state
        self._llm = llm_client
        self._memory = memory_manager

    async def tick(
        self, elapsed_hours: float, current_time: float
    ) -> list[AutonomyDecision]:
        """Run one autonomy tick for all relevant NPCs.

        Called by the Director after time advances.
        Returns decisions (which include any GameEvents to schedule).
        """
        decisions: list[AutonomyDecision] = []

        tier1_npcs, tier2_npcs = self._classify_npcs()

        # Tier 1: LLM-driven decisions for important NPCs
        for npc in tier1_npcs:
            decision = await self._decide_llm(npc, elapsed_hours, current_time)
            decisions.append(decision)

        # Tier 2: Rule-based decisions
        for npc in tier2_npcs:
            decision = self._decide_rules(npc, elapsed_hours, current_time)
            decisions.append(decision)

        return decisions

    def _classify_npcs(self) -> tuple[list[NPCCard], list[NPCCard]]:
        """Split NPCs into tier 1 (LLM) and tier 2 (rules)."""
        player_loc = self._game_state.player.location_id
        tier1: list[NPCCard] = []
        tier2: list[NPCCard] = []

        for npc in self._game_state.npcs.values():
            if npc.importance >= self.TIER1_IMPORTANCE:
                has_active_goals = any(not g.completed for g in npc.goals)
                near_player = npc.location_id == player_loc
                if near_player or has_active_goals:
                    tier1.append(npc)
                else:
                    tier2.append(npc)
            elif npc.importance >= self.TIER2_IMPORTANCE:
                tier2.append(npc)
            # else: skip (tier 3)

        return tier1, tier2

    async def _decide_llm(
        self, npc: NPCCard, elapsed_hours: float, current_time: float
    ) -> AutonomyDecision:
        """Use the LLM to decide what an important NPC does."""
        from llm.message import Message, Role

        goals_text = "\n".join(
            f"- {g.description} (priority {g.priority})"
            for g in npc.goals if not g.completed
        ) or "No active goals"

        prompt = (
            f"NPC: {npc.name} ({npc.occupation})\n"
            f"Location: {npc.location_id or 'unknown'}\n"
            f"Mood: {npc.current_mood}\n"
            f"Goals:\n{goals_text}\n"
            f"Secrets: {', '.join(npc.secrets) if npc.secrets else 'None'}\n"
            f"Fears: {', '.join(npc.fears) if npc.fears else 'None'}\n"
            f"Time elapsed: {elapsed_hours} hours\n"
            f"Current game hour: {current_time}\n\n"
            "What does this NPC do during this time? Output ONLY valid JSON:\n"
            '{"action_type": "pursue_goal|socialize|patrol|trade|scheme|travel|rest|idle",'
            ' "description": "brief 1-sentence description of what they do",'
            ' "check_type": "combat|persuasion|stealth|perception|crafting|knowledge|null",'
            ' "difficulty_class": 10}'
        )

        response = await self._llm.send_message(
            messages=[Message(role=Role.USER, content=prompt)],
            system_prompt=(
                "You decide what NPCs do off-screen in a historical text quest. "
                "Keep actions grounded in the NPC's personality, goals, and setting. "
                "Output ONLY valid JSON, nothing else."
            ),
            max_tokens=300,
        )

        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            data = {
                "action_type": "idle",
                "description": f"{npc.name} goes about their routine.",
            }

        action_str = data.get("action_type", "idle")
        try:
            action_type = NPCActionType(action_str)
        except ValueError:
            action_type = NPCActionType.IDLE

        check_type_str = data.get("check_type")
        check_type = None
        if check_type_str and check_type_str != "null":
            try:
                check_type = CheckType(check_type_str)
            except ValueError:
                pass

        dc = data.get("difficulty_class", DC_MODERATE)
        description = data.get("description", f"{npc.name} goes about their routine.")

        # Roll dice if a check is needed
        dice_outcome = None
        if check_type:
            dice_outcome = npc_skill_check(npc.attributes, check_type, dc)

        # Build resulting events if the check succeeded (or no check needed)
        events: list[GameEvent] = []
        succeeded = dice_outcome is None or dice_outcome.succeeded
        if succeeded and action_type != NPCActionType.IDLE:
            event = GameEvent(
                name=f"{npc.name}: {description}",
                scheduled_at=current_time,
                duration=0.0,  # Instant — already happened during elapsed time
                owner_id=npc.uuid,
                location_id=npc.location_id,
                scope="local",
                on_complete_description=description,
            )
            events.append(event)

            # Advance goal progress if pursuing a goal
            if action_type == NPCActionType.PURSUE_GOAL:
                active_goals = [g for g in npc.goals if not g.completed]
                if active_goals:
                    goal = max(active_goals, key=lambda g: g.priority)
                    goal.progress = min(1.0, goal.progress + 0.25)
                    if goal.progress >= 1.0:
                        goal.completed = True

        return AutonomyDecision(
            npc_id=npc.uuid,
            npc_name=npc.name,
            action_type=action_type,
            description=description,
            check_type=check_type,
            difficulty_class=dc,
            dice_outcome=dice_outcome,
            resulting_events=events,
        )

    def _decide_rules(
        self, npc: NPCCard, elapsed_hours: float, current_time: float
    ) -> AutonomyDecision:
        """Simple rule-based decision for mid-tier NPCs.

        Strategy: if the NPC has goals, pick the highest-priority
        incomplete goal and roll for it. Otherwise idle.
        """
        active_goals = [g for g in npc.goals if not g.completed]
        if not active_goals:
            return AutonomyDecision(
                npc_id=npc.uuid,
                npc_name=npc.name,
                action_type=NPCActionType.IDLE,
                description=f"{npc.name} goes about their daily routine.",
            )

        goal = max(active_goals, key=lambda g: g.priority)

        # Map goal's related_check to a CheckType
        check_type = CheckType.PERCEPTION  # default
        if goal.related_check:
            try:
                check_type = CheckType(goal.related_check)
            except ValueError:
                pass

        dice_outcome = npc_skill_check(npc.attributes, check_type, DC_MODERATE)

        # On success, advance goal progress
        events: list[GameEvent] = []
        description = f"{npc.name} works toward: {goal.description}"
        if dice_outcome.succeeded:
            goal.progress = min(1.0, goal.progress + 0.25)
            if goal.progress >= 1.0:
                goal.completed = True
                description = f"{npc.name} completed their goal: {goal.description}"

        return AutonomyDecision(
            npc_id=npc.uuid,
            npc_name=npc.name,
            action_type=NPCActionType.PURSUE_GOAL,
            description=description,
            check_type=check_type,
            dice_outcome=dice_outcome,
            resulting_events=events,
        )
