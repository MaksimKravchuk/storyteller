"""Seed state builder for the Marcus memory follow-up scenario.

Every call returns a fresh :class:`GameState`:

* Setting: "Ancient Rome, 1st century AD".
* One NPC: ``Marcus`` (baker) registered in ``game_state.npcs`` with
  ``conversation_history`` pre-populated with two short exchanges that
  establish (1) a loaf was stolen from his stall yesterday and
  (2) he suspects a man named Gaius.
* Knowledge graph: two :class:`KnowledgeNode` entries — one per fact —
  tagged as ``PERSONAL_EXPERIENCE``. Both are linked from Marcus's
  actor node via an ``EdgeType.WITNESSED`` edge so
  :class:`KnowledgeQueryEngine.get_memories_about` surfaces them when
  Marcus's Actor runs.
* Current scene: the marketplace, with Marcus already initialised
  (his ``SceneNPC.uuid`` points at his ``NPCCard.uuid``).

The player's location is set to the marketplace so Narrator's
location-resolving logic (which prefers ``player.location_id``) finds a
registered :class:`Location`.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting

_LOCATION_ID = "marketplace-forum"
_MARCUS_UUID = "npc-marcus-baker"

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


def _build_marcus_history() -> list[dict[str, str]]:
    """Materialise the canonical history as a fresh list of role/content dicts."""
    return [{"role": role, "content": body} for role, body in _MARCUS_HISTORY_PAIRS]


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


def _make_marcus() -> NPCCard:
    """Build the pre-populated Marcus card."""
    marcus = NPCCard(
        name="Marcus",
        biography="A middle-aged baker who runs a small stall at the Roman Forum marketplace.",
        appearance="Short, stocky, flour-dusted apron, broad hands.",
        occupation="baker",
        personality_traits=["earnest", "talkative", "anxious"],
        speech_style="plain, blunt, often lapses into worried mutters",
        knowledge_scope="local",
        conversation_history=_build_marcus_history(),
        current_mood="worried",
        physical_status="healthy",
        location_id=_LOCATION_ID,
    )
    # Pin a deterministic uuid so elements can reference Marcus by id.
    marcus.uuid = _MARCUS_UUID
    return marcus


def _seed_marcus_memories(graph: KnowledgeGraph, marcus_uuid: str) -> None:
    """Attach Marcus's two personal-experience memories to the graph."""
    graph.register_actor_node(marcus_uuid, label="Marcus (baker)")
    for text in (_FACT_STOLEN_LOAF, _FACT_SUSPECT_GAIUS):
        node = KnowledgeNode(
            text=text,
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            location_id=_LOCATION_ID,
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
        points_of_interest=["bread stall", "fountain", "statue of Caesar"],
    )


def _make_scene(location_id: str, marcus_uuid: str) -> Scene:
    return Scene(
        location_id=location_id,
        description=(
            "The Forum is noisy with vendors and shoppers. Marcus stands behind his bread stall, "
            "arranging loaves with distracted hands."
        ),
        npcs_present=[SceneNPC(role="baker", uuid=marcus_uuid)],
        points_of_interest=["bread stall", "fountain", "statue of Caesar"],
        ambient_description="Midday sun, smell of fresh bread and dust, a murmur of Latin bargaining.",
        time_of_day="midday",
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` for this scenario."""
    graph = KnowledgeGraph()
    marcus = _make_marcus()
    _seed_marcus_memories(graph, marcus.uuid)

    location = _make_location()
    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid),
    )
    game_state.locations[location.uuid] = location
    game_state.npcs[marcus.uuid] = marcus
    marcus.location_id = location.uuid
    game_state.current_scene = _make_scene(location.uuid, marcus.uuid)
    game_state.game_clock = 10.0  # Mid-morning.
    game_state.game_time = "morning"
    return ScenarioState(game_state=game_state, events=[])
