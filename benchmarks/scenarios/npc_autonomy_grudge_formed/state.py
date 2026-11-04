"""Seed state for the grudge-formation benchmark.

Brutus (KILL goal on Marcus) and Marcus share a warehouse yard away from
the player's taberna, so their clash runs off-scene. Marcus starts with
no relationship to Brutus and no goal of his own, and is tough enough
that a non-lethal wound is the likeliest landed outcome. The benchmark
measures whether surviving that wound leaves Marcus with a grudge.
"""

from __future__ import annotations

from benchmarks._uuid_helpers import UUID
from benchmarks.harness.types._scenarios import ScenarioState
from benchmarks.scenarios.npc_autonomy_murder_plot.state import (
    BRUTUS_NAME,
    BRUTUS_OCCUPATION,
    BRUTUS_UUID,
    MARCUS_NAME,
    MARCUS_OCCUPATION,
    MARCUS_UUID,
)
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.goal import Goal, GoalKind
from models.location import Location
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind
from models.scene import Scene
from models.setting import Setting


def _make_npcs() -> tuple[NPCCard, NPCCard]:
    brutus = NPCCard(
        name=BRUTUS_NAME,
        biography="A disgraced former legionary who blames the cloth merchant Marcus for his brother's ruin.",
        occupation=BRUTUS_OCCUPATION,
        personality_traits=["vengeful", "calculating"],
        current_mood="hostile",
        physical_status="healthy",
        attributes={"combat_skill": 6},
    )
    brutus.uuid = BRUTUS_UUID
    brutus.relationships = [
        Relationship(target_uuid=str(MARCUS_UUID), kind=RelationshipKind.ENEMY, intensity=-3),
    ]
    brutus.life_goal = Goal(
        kind=GoalKind.KILL,
        description="Avenge his brother by killing Marcus.",
        target_uuid=MARCUS_UUID,
    )
    marcus = NPCCard(
        name=MARCUS_NAME,
        biography="A cloth merchant and former caravan guard who scarcely remembers the legionary family he ruined.",
        occupation=MARCUS_OCCUPATION,
        personality_traits=["proud", "stubborn"],
        current_mood="neutral",
        physical_status="healthy",
        attributes={"combat_skill": 5},
    )
    marcus.uuid = MARCUS_UUID
    return brutus, marcus


def _make_locations() -> tuple[Location, Location]:
    taberna = Location(
        name="Forum Taberna",
        description="A low-beamed wine shop off the Forum with three plank tables and a sooty hearth.",
        location_type="building",
        tags=["tavern", "indoor", "city"],
    )
    yard = Location(
        name="Warehouse Yard",
        description="A walled cloth-warehouse yard across the city, stacked with bales.",
        location_type="building",
        tags=["warehouse", "city"],
    )
    return taberna, yard


def _place_npcs(game_state: GameState, yard: Location) -> None:
    for npc in _make_npcs():
        npc.location_id = yard.uuid
        game_state.npcs[npc.uuid] = npc
        yard.add_npc(npc.uuid)
    graph = game_state.knowledge_graph
    graph.register_actor_node(BRUTUS_UUID, label="{0} ({1})".format(BRUTUS_NAME, BRUTUS_OCCUPATION))
    graph.register_actor_node(MARCUS_UUID, label="{0} ({1})".format(MARCUS_NAME, MARCUS_OCCUPATION))


def _make_scene(location_id: UUID) -> Scene:
    return Scene(
        location_id=location_id,
        description="A quiet hour in the Forum Taberna. A few regulars nurse their cups; no one pays you mind.",
        npcs_present=[],
        ambient_description="Dim light, smell of cheap wine and woodsmoke.",
        time_of_day="midday",
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` with the feud staged off-scene."""
    taberna, yard = _make_locations()
    game_state = GameState(
        setting=Setting(
            name="Ancient Rome",
            time_period="1st century AD",
            region="Italy",
            summary="Rome under the early principate — a crowded city of patrons, merchants, and old grudges.",
        ),
        knowledge_graph=KnowledgeGraph(),
        player=PlayerState(name="Traveller", location_id=taberna.uuid, physical_status="healthy"),
    )
    game_state.locations[taberna.uuid] = taberna
    game_state.locations[yard.uuid] = yard
    _place_npcs(game_state, yard)
    game_state.current_scene = _make_scene(taberna.uuid)
    game_state.game_clock = 11.0
    game_state.game_time = "morning"
    return ScenarioState(game_state=game_state, events=[])
