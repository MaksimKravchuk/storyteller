"""Fixed fictional dialogue situations and NPC-visible memory setup."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from benchmarks.scenarios.autonomy_three_guards_tavern.state import build_state
from knowledge.node import CanonSource, EdgeType, KnowledgeNode, KnowledgeSource
from models.game_state import GameState
from models.npc_card import NPCCard

_PRIOR_MEMORY_SALIENCE = 0.95


@dataclass(frozen=True)
class Case:
    """One predeclared situation and its assessment rubric."""

    name: str
    language: str
    era: str
    location: str
    npc_name: str
    occupation: str
    biography: str
    appearance: str
    inventory: list[str]
    traits: list[str]
    speech_style: str
    scene: str
    player_action: str
    prior_memory: str | None
    expected_understanding: list[str]
    expected_expression: list[str]
    rubric: str


def load_cases() -> tuple[Case, ...]:
    """Read the fixed cases in their declared order."""
    with Path(__file__).with_name("cases.json").open(encoding="utf-8") as source:
        return tuple(Case(**entry) for entry in json.load(source))


def _is_aulus(candidate: NPCCard) -> bool:
    return candidate.name == "Aulus"


def make_state(case: Case) -> tuple[GameState, NPCCard]:
    """Build a fresh NPC whose held memory is visible through the real Actor seam."""
    state = build_state().game_state
    npc = next(filter(_is_aulus, state.npcs.values()))
    npc.name = case.npc_name
    npc.occupation = case.occupation
    npc.biography = case.biography
    npc.appearance = case.appearance
    npc.inventory = case.inventory
    npc.personality_traits = case.traits
    npc.speech_style = case.speech_style
    npc.current_mood = "neutral"
    state.setting.time_period = case.era
    if state.current_scene is not None:
        state.current_scene.description = case.scene
    if case.prior_memory:
        memory = KnowledgeNode(
            text=case.prior_memory,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            subject_id=state.player.uuid,
            timestamp=state.game_clock - 1,
            salience=_PRIOR_MEMORY_SALIENCE,
        )
        state.knowledge_graph.add_node(memory)
        state.knowledge_graph.add_edge(npc.uuid, memory.uuid, EdgeType.WITNESSED)
    return state, npc


def jev_state(case: Case) -> dict[str, object]:
    """Give Jev the same observable facts and claimed prior experience."""
    return {
        "era": case.era,
        "npc": {
            "name": case.npc_name,
            "role": case.occupation,
            "biography": case.biography,
            "appearance": case.appearance,
            "inventory": case.inventory,
            "traits": case.traits,
            "speech_style": case.speech_style,
            "current_mood": "neutral",
        },
        "scene": case.scene,
        "held_memory": case.prior_memory or "none",
        "player_action": case.player_action,
        "language": case.language,
    }
