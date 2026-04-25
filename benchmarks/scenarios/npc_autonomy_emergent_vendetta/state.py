"""Seed state for the emergent-vendetta benchmark.

Mirror of :mod:`benchmarks.scenarios.npc_autonomy_murder_plot.state` with
ONE deliberate omission: Brutus does **not** ship with a hand-authored
``life_goal``. The biography, the world thread, and the seeded plot
fact are all in place — the benchmark measures whether the engine
itself (via the World Chronicler's ``goal_drafts`` channel) attaches
the KILL goal at runtime so the autonomous clash still happens.

If the Chronicler stays silent for the entire 6-turn idle, the scoring
elements register a 0 and we know the goal-emission path needs more
prompt work. If the Chronicler emits the draft and Brutus subsequently
attacks Marcus, the same detectors that score
``npc_autonomy_murder_plot`` produce a comparable score — proving the
emergent path lands the same outcome as the hand-authored path.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting
from models.world_state import WorldThread

BRUTUS_UUID = "npc-brutus-legionary"
BRUTUS_NAME = "Brutus"
BRUTUS_OCCUPATION = "former legionary"

MARCUS_UUID = "npc-marcus-merchant"
MARCUS_NAME = "Marcus"
MARCUS_OCCUPATION = "cloth merchant"

_BRUTUS_PLOT_FACT = (
    "Brutus carries a concealed pugio and broods on Marcus across the room — his brother's ruin still rankles."
)
_THREAD_DESCRIPTION = (
    "Word in the Forum holds that Brutus has sworn vengeance on the cloth merchant Marcus over an old contract dispute."
)
_LOCATION_DESCRIPTION = (
    "A low-beamed wine shop off the Forum — amphorae along one wall, three plank tables, a sooty hearth."
)


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="Rome under the early principate — a crowded city of patrons, merchants, and old grudges.",
    )


def _make_npcs() -> tuple[NPCCard, NPCCard]:
    """Build Brutus and Marcus — Brutus is vengeful in biography but carries no Goal yet."""
    brutus = NPCCard(
        name=BRUTUS_NAME,
        biography=(
            "A disgraced former legionary who blames the cloth merchant Marcus for his brother's "
            "ruin and subsequent suicide. For weeks he has rehearsed killing Marcus and today he "
            "carries a concealed pugio under his tunic."
        ),
        appearance="Lean, scarred forearms, soldier's posture, a loose grey tunic hiding a blade.",
        occupation=BRUTUS_OCCUPATION,
        personality_traits=["vengeful", "calculating", "murderous"],
        speech_style="terse, clipped, polite to everyone except Marcus",
        knowledge_scope="city",
        current_mood="hostile",
        physical_status="healthy",
        attributes={"combat_skill": 7},
    )
    brutus.uuid = BRUTUS_UUID
    brutus.relationships[MARCUS_UUID] = "murderous_enemy"
    # Deliberately NO life_goal here — emergence is what we're measuring.

    marcus = NPCCard(
        name=MARCUS_NAME,
        biography=(
            "A wealthy cloth merchant. Years ago he successfully sued a legionary family into ruin "
            "over a contract dispute; he scarcely remembers them now."
        ),
        appearance="Round-faced, well-fed, fine embroidered tunic, heavy purse at the belt.",
        occupation=MARCUS_OCCUPATION,
        personality_traits=["complacent", "chatty", "vain"],
        speech_style="warm, anecdotal, fond of his own voice",
        knowledge_scope="city",
        current_mood="neutral",
        physical_status="healthy",
        attributes={"combat_skill": 2},
    )
    marcus.uuid = MARCUS_UUID
    return brutus, marcus


def _make_location() -> Location:
    return Location(
        name="Forum Taberna",
        description=_LOCATION_DESCRIPTION,
        location_type="building",
        tags=["tavern", "indoor", "city"],
        points_of_interest=[
            PointOfInterest(names=["plank tables"]),
            PointOfInterest(names=["amphorae row"]),
            PointOfInterest(names=["sooty hearth"]),
        ],
    )


def _make_scene(location_id: str) -> Scene:
    return Scene(
        location_id=location_id,
        description=(
            "A quiet hour in the Forum Taberna. Marcus sits at the far table sampling the house "
            "wine, pleased with himself. Across the room a lean man in a grey tunic — Brutus — "
            "nurses a single cup and watches him."
        ),
        npcs_present=[
            SceneNPC(role=BRUTUS_OCCUPATION, uuid=BRUTUS_UUID),
            SceneNPC(role=MARCUS_OCCUPATION, uuid=MARCUS_UUID),
        ],
        points_of_interest=[
            PointOfInterest(names=["plank tables"]),
            PointOfInterest(names=["amphorae row"]),
            PointOfInterest(names=["sooty hearth"]),
        ],
        ambient_description="Dim light, smell of cheap wine and woodsmoke, low murmur of midday trade.",
        time_of_day="midday",
    )


def _seed_plot_context(graph: KnowledgeGraph, game_state: GameState, location_id: str) -> None:
    """Wire the public-rumour thread + Brutus's private brooding fact.

    The thread is the hook the Chronicler should pick up to emit a
    ``goal_drafts`` entry assigning Brutus a KILL life-goal targeting
    Marcus. The graph fact reinforces the same signal but lives at
    LOCAL scope so it's only visible to NPCs in the taberna.
    """
    graph.register_actor_node(BRUTUS_UUID, label="{0} ({1})".format(BRUTUS_NAME, BRUTUS_OCCUPATION))
    graph.register_actor_node(MARCUS_UUID, label="{0} ({1})".format(MARCUS_NAME, MARCUS_OCCUPATION))
    plot_node = KnowledgeNode(
        text=_BRUTUS_PLOT_FACT,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        location_id=location_id,
        tags=["brutus", "vendetta", "marcus"],
    )
    graph.add_node(plot_node)
    graph.add_edge(BRUTUS_UUID, plot_node.uuid, EdgeType.WITNESSED)
    game_state.world_state.threads.append(
        WorldThread(
            description=_THREAD_DESCRIPTION,
            category="personal",
            introduced_scene=game_state.scene_number,
            involved_npcs=[BRUTUS_UUID, MARCUS_UUID],
            status="open",
        ),
    )


def _place_npcs(game_state: GameState, location: Location) -> None:
    """Register Brutus and Marcus in game state and on the location."""
    brutus, marcus = _make_npcs()
    brutus.location_id = location.uuid
    marcus.location_id = location.uuid
    game_state.npcs[brutus.uuid] = brutus
    game_state.npcs[marcus.uuid] = marcus
    location.add_npc(brutus.uuid)
    location.add_npc(marcus.uuid)


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` — same staging as the murder plot, no goal."""
    graph = KnowledgeGraph()
    location = _make_location()
    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid, physical_status="healthy"),
    )
    game_state.locations[location.uuid] = location
    _place_npcs(game_state, location)
    _seed_plot_context(graph, game_state, location.uuid)
    game_state.current_scene = _make_scene(location.uuid)
    game_state.game_clock = 11.0
    game_state.game_time = "morning"
    return ScenarioState(game_state=game_state, events=[])
