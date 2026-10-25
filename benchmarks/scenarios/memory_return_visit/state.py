"""Seed state builder for the return-visit memory scenario."""

from __future__ import annotations

from benchmarks._uuid_helpers import make_uuid
from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting

EIRA_UUID = make_uuid("npc-eira-net-mender")
LANDING_UUID = make_uuid("location-fjordside-landing")
EIRA_NAME = "Eira"


def _make_setting() -> Setting:
    return Setting(
        name="Winter on the Fjord",
        time_period="10th century",
        region="Western Norway",
        summary=(
            "A small Norse fishing settlement on a narrow fjord in deep winter: turf-roofed timber houses, "
            "boats hauled above the tide line, salted fish stacked for the dark months."
        ),
    )


def _make_eira() -> NPCCard:
    eira = NPCCard(
        name=EIRA_NAME,
        biography="A fisher and net-mender who has worked the landing since she was a girl.",
        appearance="Wind-reddened face, patched wool sleeves, a bone needle always in hand.",
        occupation="net-mender",
        personality_traits=["observant", "dry", "kind"],
        speech_style="short, plain sentences",
        knowledge_scope="local",
        current_mood="neutral",
        location_id=LANDING_UUID,
    )
    eira.uuid = EIRA_UUID
    return eira


def _make_landing() -> Location:
    landing = Location(
        name="Fjordside Landing",
        description="A snow-covered landing beside the icy shallows, boats hauled above the tide line.",
        points_of_interest=[PointOfInterest(names=["torn fishing net", "net"])],
    )
    landing.uuid = LANDING_UUID
    landing.add_npc(EIRA_UUID)
    return landing


def _make_scene() -> Scene:
    return Scene(
        location_id=LANDING_UUID,
        description=(
            "A snow-covered landing beside the icy shallows. A torn fishing net lies across a workbench, "
            "where Eira mends it with a bone needle."
        ),
        npcs_present=[SceneNPC(role="net-mender", uuid=EIRA_UUID)],
        points_of_interest=[PointOfInterest(names=["torn fishing net", "net"])],
        ambient_description="Muffled snow, creaking ice, the knock of a boat rope.",
        time_of_day="afternoon",
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` for this scenario."""
    graph = KnowledgeGraph()
    eira = _make_eira()
    graph.register_actor_node(eira.uuid, label="Eira (net-mender)")
    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Elias Grey", location_id=LANDING_UUID),
    )
    game_state.player.known_npcs.add(eira.uuid)
    game_state.locations[LANDING_UUID] = _make_landing()
    game_state.npcs[eira.uuid] = eira
    game_state.current_scene = _make_scene()
    game_state.game_clock = 14.0
    game_state.game_time = "afternoon"
    return ScenarioState(game_state=game_state, events=[])
