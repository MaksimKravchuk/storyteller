"""Fixed fictional inputs for the NPC reaction comparison."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from benchmarks.scenarios.autonomy_three_guards_tavern.state import build_state
from models.game_state import GameState
from models.npc_card import NPCCard


@dataclass(frozen=True)
class Case:
    """One controlled situation presented to each decision method."""

    name: str
    mood: str
    role: str
    traits: list[str]
    scene: str
    player_action: str
    language: str = "English"


def load_cases() -> tuple[Case, ...]:
    """Load the preregistered situations in stable order."""
    with Path(__file__).with_name("cases.json").open(encoding="utf-8") as source:
        entries = json.load(source)
    return tuple(Case(**entry) for entry in entries)


def _apply_role(npc: NPCCard, role: str) -> None:
    """Keep each Actor's biography and equipment aligned with its role."""
    if role == "merchant":
        npc.biography = "A market trader with a family, used to avoiding street violence."
        npc.appearance = "Plain tunic, no armor or weapon."
        npc.inventory = ["purse", "market goods"]
        npc.speech_style = "cautious and practical"
    elif role == "bandit":
        npc.biography = "A street bandit who guards stolen goods fiercely."
        npc.appearance = "Travel-worn clothes, dagger at the belt."
        npc.inventory = ["dagger", "bag of goods"]
        npc.speech_style = "blunt and confrontational"


def _is_aulus(candidate: NPCCard) -> bool:
    return candidate.name == "Aulus"


def make_state(case: Case) -> tuple[GameState, NPCCard]:
    """Start each call from a fresh copy of the tavern benchmark state."""
    state = build_state().game_state
    npc = next(filter(_is_aulus, state.npcs.values()))
    npc.current_mood = case.mood
    npc.occupation = case.role
    npc.personality_traits = case.traits
    _apply_role(npc, case.role)
    if state.current_scene is not None:
        state.current_scene.description = case.scene
    return state, npc


def jev_state(case: Case) -> dict[str, object]:
    """Give Jev the facts also available to the real Actor prompt."""
    _game_state, npc = make_state(case)
    return {
        "npc": {
            "name": npc.name,
            "role": npc.occupation,
            "biography": npc.biography,
            "appearance": npc.appearance,
            "speech_style": npc.speech_style,
            "inventory": npc.inventory,
            "mood": npc.current_mood,
            "physical_status": npc.physical_status,
            "traits": npc.personality_traits,
        },
        "scene": case.scene,
        "last_player_action": case.player_action,
        "language": case.language,
    }
