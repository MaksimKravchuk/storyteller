"""Seed state for the npc-generator role-fidelity benchmark.

A small market plaza adjacent to the Temple of Vesta, seeded with one
open world thread that names a blind beggar and a Roman senator. The
seed deliberately ships no NPCs in the scene — the player's first
turn triggers Director→NPCGenerator for the beggar, the third turn
triggers it for the senator.
"""

from __future__ import annotations

from benchmarks._uuid_helpers import UUID, make_uuid
from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.location import Location
from models.scene import PointOfInterest, Scene
from models.setting import Setting
from models.world_state import WorldThread

MARKET_UUID = make_uuid("scenario-vesta-market")

_THREAD_DESCRIPTION = (
    "A blind beggar haunts the steps of the Temple of Vesta. A Roman senator visits weekly to give "
    "alms; the next visit is rumoured to be today."
)
_LOCATION_DESCRIPTION = (
    "A small market plaza adjacent to the Temple of Vesta — stone steps to the north, a low "
    "fountain at the centre, a single fig-tree in the corner."
)
_SCENE_DESCRIPTION = (
    "Mid-morning at the Vesta market plaza. The temple steps glare white in the sun; the fountain "
    "drips into its basin; the plaza is between the rush of dawn and the noon crowd."
)


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="Rome under the early principate — a public market plaza near the Temple of Vesta.",
    )


def _make_location() -> Location:
    location = Location(
        name="Temple of Vesta market plaza",
        description=_LOCATION_DESCRIPTION,
        location_type="plaza",
        tags=["public", "religious", "outdoor"],
        points_of_interest=[
            PointOfInterest(names=["temple steps"]),
            PointOfInterest(names=["fountain"]),
            PointOfInterest(names=["fig-tree"]),
        ],
    )
    # Pin to ``MARKET_UUID`` so future location-keyed checks (none today)
    # can look it up by the constant rather than a drifting ``uuid4()``.
    location.uuid = MARKET_UUID
    return location


def _make_scene(location_id: UUID) -> Scene:
    return Scene(
        location_id=location_id,
        description=_SCENE_DESCRIPTION,
        npcs_present=[],
        points_of_interest=[
            PointOfInterest(names=["temple steps"]),
            PointOfInterest(names=["fountain"]),
            PointOfInterest(names=["fig-tree"]),
        ],
        ambient_description=(
            "Bright sun on white marble, soft drip of fountain water, distant chant from inside the temple."
        ),
        time_of_day="morning",
    )


def _seed_thread(game_state: GameState) -> None:
    """Plant the rumour thread that names the two roles the script will spawn."""
    game_state.world_state.threads.append(
        WorldThread(
            description=_THREAD_DESCRIPTION,
            category="social",
            introduced_scene=game_state.scene_number,
            status="open",
        ),
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` — solo player in an NPC-free market plaza."""
    graph = KnowledgeGraph()
    location = _make_location()
    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid, physical_status="healthy"),
    )
    game_state.locations[location.uuid] = location
    game_state.current_scene = _make_scene(location.uuid)
    _seed_thread(game_state)
    game_state.game_clock = 10.0
    game_state.game_time = "morning"
    return ScenarioState(game_state=game_state, events=[])
