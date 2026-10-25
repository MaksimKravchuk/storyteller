"""Who sits out an NPC autonomous turn when the player addressed someone.

On a non-aggressive turn where an NPC already answered the player, a
routine NPC's autonomous turn only re-answers the question or repeats a
gesture. Only NPCs with their own reason to act keep the turn.
"""

from __future__ import annotations

from cast import npc_opportunity as _npo
from models.game_state import GameState
from models.goal import GoalStatus
from models.npc_card import NPCCard


def has_own_reason_to_act(npc: NPCCard, game_state: GameState) -> bool:
    """True when the NPC is hostile, mid tactical goal, or faces a target of standing intent."""
    if npc.hostility_level > 0 or _in_tactical_goal(npc):
        return True
    return _npo.get_opportunity_clause(npc, game_state) is not None


def _in_tactical_goal(npc: NPCCard) -> bool:
    tactical = npc.tactical_goal
    return tactical is not None and tactical.status is GoalStatus.ACTIVE
