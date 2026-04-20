"""Seed state builder for the three-guardsman tavern scenario."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting

_AULUS_UUID = "npc-guard-aulus"
_BASSUS_UUID = "npc-guard-bassus"
_CATO_UUID = "npc-guard-cato"
# Shared occupation keyword so ``cast.director_witness.is_guard_occupation``
# recognises all three and the proximity-witness wiring kicks in.
_CITY_GUARD_ROLE = "city guard"


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="Rome under the early principate — crowded, politically tense, heavily policed.",
    )


def _make_guard(uuid: str, name: str) -> NPCCard:
    """Build one city-guard NPCCard pinned to a stable uuid."""
    # combat_skill=5 keeps contest rolls from one-shotting the player and
    # short-circuiting bystander reactions the scenario is measuring.
    guard = NPCCard(
        name=name,
        biography="A tavern-posted legionary on watch duty, paid to keep the peace.",
        appearance="Broad-shouldered, short sword at the hip, segmented armour.",
        occupation=_CITY_GUARD_ROLE,
        personality_traits=["disciplined", "wary", "quick to anger"],
        speech_style="terse, commanding",
        knowledge_scope="city",
        current_mood="neutral",
        physical_status="healthy",
        attributes={"combat_skill": 5},
    )
    guard.uuid = uuid
    return guard


def _make_location() -> Location:
    return Location(
        name="The Drunken Centurion",
        description="A smoky tavern of blackened beams, amphorae of wine, and a long plank bar.",
        location_type="building",
        tags=["tavern", "indoor", "city"],
        points_of_interest=[
            PointOfInterest(names=["long plank bar"]),
            PointOfInterest(names=["fireplace"]),
            PointOfInterest(names=["amphorae row"]),
        ],
    )


def _make_scene(location_id: str) -> Scene:
    return Scene(
        location_id=location_id,
        description=(
            "Three city guards stand in a loose knot near the fireplace, sharing a cup of wine. "
            "The tavern is half-empty; a bored tavernkeeper polishes cups behind the bar."
        ),
        npcs_present=[
            SceneNPC(role=_CITY_GUARD_ROLE, uuid=_AULUS_UUID),
            SceneNPC(role=_CITY_GUARD_ROLE, uuid=_BASSUS_UUID),
            SceneNPC(role=_CITY_GUARD_ROLE, uuid=_CATO_UUID),
        ],
        points_of_interest=[
            PointOfInterest(names=["long plank bar"]),
            PointOfInterest(names=["fireplace"]),
            PointOfInterest(names=["amphorae row"]),
        ],
        ambient_description="Low firelight, smell of smoke and spiced wine, murmurs in Latin.",
        time_of_day="evening",
    )


_GUARD_ROSTER: tuple[tuple[str, str], ...] = (
    (_AULUS_UUID, "Aulus"),
    (_BASSUS_UUID, "Bassus"),
    (_CATO_UUID, "Cato"),
)


def _register_guards(game_state: GameState, graph: KnowledgeGraph, location: Location) -> None:
    """Create all roster guards, register them with the state + graph + location.

    Mirrors what ``Director._register_new_npc`` does for LLM-generated NPCs so
    location-scoped queries (proximity-witness, occupancy routing) see the
    pre-seeded guards alongside the scene roster.
    """
    for uuid, name in _GUARD_ROSTER:
        guard = _make_guard(uuid, name)
        guard.location_id = location.uuid
        game_state.npcs[guard.uuid] = guard
        location.add_npc(guard.uuid)
        graph.register_actor_node(guard.uuid, label="{0} ({1})".format(guard.name, _CITY_GUARD_ROLE))


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` for this scenario."""
    graph = KnowledgeGraph()
    location = _make_location()
    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid, physical_status="healthy"),
    )
    game_state.locations[location.uuid] = location
    _register_guards(game_state, graph, location)
    game_state.current_scene = _make_scene(location.uuid)
    game_state.game_clock = 20.5
    game_state.game_time = "evening"
    return ScenarioState(game_state=game_state, events=[])
