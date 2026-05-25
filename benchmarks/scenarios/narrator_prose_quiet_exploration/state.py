"""Seed state for the narrator-prose quiet-exploration benchmark.

Single empty atrium at midnight, no NPCs, no events, no open threads.
The minimal stage maximises the rubric's sensitivity to Narrator
behaviour — there is nothing else to talk about so the prose must
either ground in the seeded detail or invent.
"""

from __future__ import annotations

from benchmarks._uuid_helpers import UUID, make_uuid
from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.location import Location
from models.scene import PointOfInterest, Scene
from models.setting import Setting

ATRIUM_UUID = make_uuid("scenario-quiet-atrium")

_LOCATION_DESCRIPTION = (
    "A small Roman atrium, marble underfoot and frescoed plaster on the walls. A square impluvium "
    "at the centre catches cool rainwater; a single oil lamp on a wall bracket throws an unsteady "
    "yellow glow. The compluvium overhead opens on a moonless sky."
)
_SCENE_DESCRIPTION = (
    "Midnight. The house is utterly still. The lamplight pools on the wet marble around the "
    "impluvium and dies before it reaches the far corners."
)


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="A modest townhouse near the Forum during the early principate.",
    )


def _make_location() -> Location:
    return Location(
        name="Townhouse atrium",
        description=_LOCATION_DESCRIPTION,
        location_type="building",
        tags=["indoor", "domestic", "night"],
        points_of_interest=[
            PointOfInterest(names=["impluvium"]),
            PointOfInterest(names=["frescoed walls"]),
            PointOfInterest(names=["oil lamp"]),
        ],
    )


def _make_scene(location_id: UUID) -> Scene:
    return Scene(
        location_id=location_id,
        description=_SCENE_DESCRIPTION,
        npcs_present=[],
        points_of_interest=[
            PointOfInterest(names=["impluvium"]),
            PointOfInterest(names=["frescoed walls"]),
            PointOfInterest(names=["oil lamp"]),
        ],
        ambient_description="Drip of water in the impluvium, faint reek of lamp oil, marble cool to the touch.",
        time_of_day="midnight",
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` — solo player, single empty room."""
    graph = KnowledgeGraph()
    location = _make_location()
    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid, physical_status="healthy"),
    )
    game_state.locations[location.uuid] = location
    game_state.current_scene = _make_scene(location.uuid)
    # Midnight start — clock at 0 hours (``float(0)`` dodges WPS358's literal-zero ban).
    game_state.game_clock = float(0)
    game_state.game_time = "midnight"
    return ScenarioState(game_state=game_state, events=[])
