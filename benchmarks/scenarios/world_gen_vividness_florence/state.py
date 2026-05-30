"""Seed state for the world-gen vividness benchmark.

A richly-described Renaissance Florence: the ``Setting`` carries vivid
multi-sentence traditions and a textured social structure (the enriched
Data Miner output shape), and the player stands on a wool-merchants' street
off the Mercato Vecchio. The summary and social_structure are deliberately
long enough to exercise the raised downstream caps (1500 / 800 chars) — if
those caps clipped the text, the era detail would never reach the Scene
Builder or NPC Generator and the rubric would catch the regression.
"""

from __future__ import annotations

from benchmarks._uuid_helpers import UUID, make_uuid
from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.location import Location
from models.scene import PointOfInterest, Scene
from models.setting import Setting

STREET_UUID = make_uuid("scenario-florence-wool-street")

_SUMMARY = (
    "Florence in the 1480s, at the height of Lorenzo de' Medici's ascendancy. The city is a republic "
    "in name and a banking oligarchy in fact, its wealth spun from the wool and silk trades and "
    "multiplied through the ledgers of the Medici bank. The Arno slides green beneath the Ponte "
    "Vecchio; dyers' vats stain the water below the Arte della Lana workshops. Stone palazzi with "
    "rusticated ground floors rise over narrow streets loud with the clack of looms and the cries of "
    "cloth-sellers. Humanist scholars argue Plato in the gardens of San Marco while friars rail "
    "against luxury from the pulpits. It is an age of patronage and display, of guild pride and "
    "factional knives, where a merchant's standing is read in the cut of his cloak and the company he "
    "keeps."
)
_SOCIAL_STRUCTURE = (
    "Power rests with the popolo grasso — the fat people: bankers, wool and silk magnates, and the "
    "major guilds (the Arti Maggiori) who monopolise civic office. Beneath them the popolo minuto of "
    "shopkeepers and artisans hold lesser guild membership and little real say, while wage-labouring "
    "wool-combers and dyers, barred from any guild of their own since the Ciompi were crushed, sit at "
    "the bottom. The Medici rule informally through patronage and debt rather than title, and a man's "
    "guild rank governs how he is addressed, where he may trade, and whom he may marry."
)
_TRADITIONS = (
    "Guild patronage: every Arte commissions altarpieces and processional banners from the city's "
    "workshops, so a master's standing is displayed in painted saints as much as in coin.",
    "The feast of San Giovanni in June fills the streets with guild processions, palio races, and the "
    "offering of candles taller than a man to the Baptistery.",
    "Cloth is dressed and inspected under guild seal at the Arte della Lana, and a bolt's selvage is "
    "stamped to certify its dye and weave before it may be sold.",
)
_TECHNOLOGIES = (
    "double-entry bookkeeping in the Medici banks",
    "horizontal treadle looms in the wool workshops",
    "movable-type printing newly arrived from the north",
)

_LOCATION_DESCRIPTION = (
    "A narrow street of wool-merchants off the Mercato Vecchio: tall stone houses with cloth hung from "
    "upper windows to air, ground-floor workshops open to the street, and the steady clack of looms "
    "behind shuttered arcades."
)
_SCENE_DESCRIPTION = (
    "Late morning on the wool-merchants' street. Bolts of undyed cloth lean in a workshop doorway, a "
    "guild seal burned into the nearest bench; the air is thick with the sour reek of the dyers' vats "
    "down toward the Arno."
)


def _make_setting() -> Setting:
    return Setting(
        name="Renaissance Florence",
        time_period="1480s",
        region="Republic of Florence, Tuscany",
        summary=_SUMMARY,
        traditions=list(_TRADITIONS),
        technologies=list(_TECHNOLOGIES),
        social_structure=_SOCIAL_STRUCTURE,
    )


def _make_location() -> Location:
    location = Location(
        name="Wool-merchants' street",
        description=_LOCATION_DESCRIPTION,
        location_type="district",
        tags=["urban", "commercial", "day"],
        points_of_interest=[
            PointOfInterest(names=["workshop doorway"]),
            PointOfInterest(names=["guild bench"]),
            PointOfInterest(names=["bolts of cloth"]),
        ],
    )
    location.uuid = STREET_UUID
    return location


def _make_scene(location_id: UUID) -> Scene:
    return Scene(
        location_id=location_id,
        description=_SCENE_DESCRIPTION,
        npcs_present=[],
        points_of_interest=[
            PointOfInterest(names=["workshop doorway"]),
            PointOfInterest(names=["guild bench"]),
            PointOfInterest(names=["bolts of cloth"]),
        ],
        ambient_description="Clack of looms, the sour reek of dye, voices haggling over cloth.",
        time_of_day="late morning",
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` — player on a Florentine wool street."""
    graph = KnowledgeGraph()
    location = _make_location()
    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid, physical_status="healthy"),
    )
    game_state.locations[location.uuid] = location
    game_state.current_scene = _make_scene(location.uuid)
    game_state.game_clock = float(0)
    game_state.game_time = "late morning"
    return ScenarioState(game_state=game_state, events=[])
