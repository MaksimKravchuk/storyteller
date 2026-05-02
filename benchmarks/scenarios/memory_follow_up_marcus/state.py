"""Seed state builder for the Marcus memory follow-up scenario."""

from __future__ import annotations

from uuid import UUID

from benchmarks._uuid_helpers import make_uuid
from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting

_MARCUS_UUID = make_uuid("npc-marcus-baker")

_ROLE_USER = "user"
_ROLE_ASSISTANT = "assistant"

_MARCUS_HISTORY_PAIRS: tuple[tuple[str, str], ...] = (
    (_ROLE_USER, "Tell me how business is, Marcus."),
    (
        _ROLE_ASSISTANT,
        (
            "Terrible, friend. Yesterday a loaf was stolen right from my stall while I was "
            "measuring flour. A whole wheat loaf, crusty and warm."
        ),
    ),
    (_ROLE_USER, "Do you know who took it?"),
    (
        _ROLE_ASSISTANT,
        (
            "I suspect Gaius — the scarred fellow who loiters by the fountain. He has been "
            "watching my stall for weeks now. I cannot prove it, but I am certain it was him."
        ),
    ),
)


_FACT_STOLEN_LOAF = "A wheat loaf was stolen from my market stall yesterday while I was measuring flour."
_FACT_SUSPECT_GAIUS = (
    "I suspect Gaius — the scarred fellow who loiters by the fountain — of stealing my loaf yesterday."
)


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The Roman Empire under the early principate — a dense, bustling, politically tense city.",
    )


def _make_marcus_base() -> NPCCard:
    """Build the Marcus card without any conversation history."""
    marcus = NPCCard(
        name="Marcus",
        biography="A middle-aged baker who runs a small stall at the Roman Forum marketplace.",
        appearance="Short, stocky, flour-dusted apron, broad hands.",
        occupation="baker",
        personality_traits=["earnest", "talkative", "anxious"],
        speech_style="plain, blunt, often lapses into worried mutters",
        knowledge_scope="local",
        conversation_history=[],
        current_mood="worried",
        physical_status="healthy",
    )
    marcus.uuid = _MARCUS_UUID
    return marcus


def _make_marcus() -> NPCCard:
    """Build the pre-populated Marcus card with seeded conversation history."""
    marcus = _make_marcus_base()
    marcus.conversation_history = [{"role": role, "content": body} for role, body in _MARCUS_HISTORY_PAIRS]
    return marcus


def _seed_marcus_memories(graph: KnowledgeGraph, marcus_uuid: UUID, location_id: UUID) -> None:
    """Attach Marcus's two personal-experience memories to the graph."""
    graph.register_actor_node(marcus_uuid, label="Marcus (baker)")
    for text in (_FACT_STOLEN_LOAF, _FACT_SUSPECT_GAIUS):
        node = KnowledgeNode(
            text=text,
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            location_id=location_id,
            tags=["marcus", "stolen-loaf"],
        )
        graph.add_node(node)
        graph.add_edge(marcus_uuid, node.uuid, EdgeType.WITNESSED)


def _make_location() -> Location:
    return Location(
        name="Roman Forum marketplace",
        description="A sun-bright plaza of stalls and pillars, dense with shoppers and the smell of bread.",
        location_type="district",
        tags=["market", "forum", "city"],
        points_of_interest=[
            PointOfInterest(names=["bread stall"]),
            PointOfInterest(names=["fountain"]),
            PointOfInterest(names=["statue of Caesar"]),
        ],
    )


def _make_scene(location_id: UUID, marcus_uuid: UUID) -> Scene:
    return Scene(
        location_id=location_id,
        description=(
            "The Forum is noisy with vendors and shoppers. Marcus stands behind his bread stall, "
            "arranging loaves with distracted hands."
        ),
        npcs_present=[SceneNPC(role="baker", uuid=marcus_uuid)],
        points_of_interest=[
            PointOfInterest(names=["bread stall"]),
            PointOfInterest(names=["fountain"]),
            PointOfInterest(names=["statue of Caesar"]),
        ],
        ambient_description="Midday sun, smell of fresh bread and dust, a murmur of Latin bargaining.",
        time_of_day="midday",
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` for this scenario."""
    graph = KnowledgeGraph()
    marcus = _make_marcus()

    location = _make_location()
    # Memory nodes and Marcus must both pin to the same location id as the
    # registered Location, or scope-filtered memory lookups go blind.
    _seed_marcus_memories(graph, marcus.uuid, location.uuid)
    marcus.location_id = location.uuid

    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid),
    )
    game_state.locations[location.uuid] = location
    game_state.npcs[marcus.uuid] = marcus
    game_state.current_scene = _make_scene(location.uuid, marcus.uuid)
    game_state.game_clock = 10.0
    game_state.game_time = "morning"
    return ScenarioState(game_state=game_state, events=[])
