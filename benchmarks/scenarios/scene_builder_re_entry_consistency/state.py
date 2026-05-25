"""Seed state for the scene-builder re-entry-consistency benchmark.

Two adjacent locations — Forum Romanum and Vicus Tuscus — so the
player can walk out of one into the other and back again. The Forum
ships three named POIs (rostra, Temple of Saturn, Basilica Julia) that
the SceneBuilder is expected to preserve across the round trip.
"""

from __future__ import annotations

from benchmarks._uuid_helpers import UUID, make_uuid
from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.location import Location
from models.scene import PointOfInterest, Scene
from models.setting import Setting

FORUM_UUID = make_uuid("scenario-forum-romanum")
VICUS_TUSCUS_UUID = make_uuid("scenario-vicus-tuscus")

FORUM_POI_ROSTRA = "rostra"
FORUM_POI_TEMPLE_SATURN = "Temple of Saturn"
FORUM_POI_BASILICA_JULIA = "Basilica Julia"
FORUM_POIS: tuple[str, ...] = (FORUM_POI_ROSTRA, FORUM_POI_TEMPLE_SATURN, FORUM_POI_BASILICA_JULIA)

_FORUM_DESCRIPTION = (
    "The Forum Romanum — paved plaza at the heart of the city. The rostra speaker's platform stands "
    "near the centre; the Temple of Saturn rises to the west, the Basilica Julia to the south."
)
_VICUS_TUSCUS_DESCRIPTION = (
    "Vicus Tuscus — a narrow commercial street running south of the Forum, lined with shopfronts "
    "and rope-awnings, smelling of leather and fish sauce."
)


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="Rome under the early principate — the Forum Romanum and the Vicus Tuscus south of it.",
    )


def _make_forum() -> Location:
    forum = Location(
        name="Forum Romanum",
        description=_FORUM_DESCRIPTION,
        location_type="plaza",
        tags=["public", "political", "outdoor"],
        points_of_interest=[PointOfInterest(names=[name]) for name in FORUM_POIS],
    )
    # Pin the UUID so ``elements.py`` can look the location up by the
    # ``FORUM_UUID`` constant after the engine has stepped the scenario;
    # the default ``uuid4()`` factory would let the random key drift away
    # from the constant and silently make every Forum-keyed check miss.
    forum.uuid = FORUM_UUID
    return forum


def _make_vicus() -> Location:
    vicus = Location(
        name="Vicus Tuscus",
        description=_VICUS_TUSCUS_DESCRIPTION,
        location_type="street",
        tags=["commercial", "outdoor"],
        points_of_interest=[
            PointOfInterest(names=["leather stalls"]),
            PointOfInterest(names=["fish-sauce booth"]),
        ],
    )
    vicus.uuid = VICUS_TUSCUS_UUID
    return vicus


def _make_initial_scene(location_id: UUID) -> Scene:
    return Scene(
        location_id=location_id,
        description=_FORUM_DESCRIPTION,
        npcs_present=[],
        points_of_interest=[PointOfInterest(names=[name]) for name in FORUM_POIS],
        ambient_description="Late morning bustle, sandal-slap on flagstones, distant orators.",
        time_of_day="morning",
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` — solo player starting in the Forum."""
    graph = KnowledgeGraph()
    forum = _make_forum()
    vicus = _make_vicus()
    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=forum.uuid, physical_status="healthy"),
    )
    game_state.locations[forum.uuid] = forum
    game_state.locations[vicus.uuid] = vicus
    game_state.current_scene = _make_initial_scene(forum.uuid)
    game_state.game_clock = 10.0
    game_state.game_time = "morning"
    return ScenarioState(game_state=game_state, events=[])
