"""Shared pytest fixtures and Allure-label enforcement."""

from __future__ import annotations

from tests import _db_stubs  # noqa: F401

import pytest
from loguru import logger

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.setting import Setting

_REQUIRED_ALLURE_LABELS = ("epic", "feature", "story")
_E2E_DIR_PART = "e2e"
_TAXONOMY_DOC = "tests/TEST_TAXONOMY.md"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Fail collection if any non-e2e test is missing required Allure labels.

    Every unit test must carry ``@allure.epic``, ``@allure.feature``,
    ``@allure.story``, and ``@allure.title`` so the rendered Allure tree reads
    as a product spec. Tests under ``tests/e2e/`` are exempt — they use a
    smaller label set and have their own audience. See ``tests/TEST_TAXONOMY.md``
    for the epic/feature reference and ``tests/README.md`` for the rationale.
    """
    violations: list[str] = []

    for item in items:
        if _is_e2e_item(item):
            continue

        labels_present = _collect_allure_label_types(item)
        title_present = _has_allure_title(item)

        missing = [label for label in _REQUIRED_ALLURE_LABELS if label not in labels_present]
        if not title_present:
            missing.append("title")

        if missing:
            violations.append("  {0}: missing {1}".format(item.nodeid, ", ".join(missing)))

    if violations:
        raise pytest.UsageError(
            "\n".join(
                [
                    "Allure label enforcement: {0} test(s) are missing required labels.".format(len(violations)),
                    "",
                    "Every unit test must carry @allure.epic, @allure.feature, @allure.story, and @allure.title.",
                    "See {0} for the epic/feature reference and tests/README.md for examples.".format(_TAXONOMY_DOC),
                    "",
                    "Violations:",
                    *violations,
                ]
            )
        )


def _is_e2e_item(item: pytest.Item) -> bool:
    return _E2E_DIR_PART in item.path.parts


def _collect_allure_label_types(item: pytest.Item) -> set[str]:
    """Return the set of allure label types attached to a pytest item.

    ``allure.epic("X")`` becomes ``pytest.mark.allure_label("X", label_type="epic")``,
    so we walk every ``allure_label`` marker (which includes class- and module-level
    decorators) and harvest the ``label_type`` kwarg.
    """
    label_types: set[str] = set()
    for mark in item.iter_markers(name="allure_label"):
        label_type = mark.kwargs.get("label_type")
        if label_type:
            label_types.add(label_type)
    return label_types


def _has_allure_title(item: pytest.Item) -> bool:
    """``allure.title`` sets ``__allure_display_name__`` on the underlying function."""
    func = getattr(item, "function", None)
    return bool(getattr(func, "__allure_display_name__", None))


@pytest.fixture
def loguru_sink():
    """Capture loguru records during a test without disturbing other handlers."""
    records = []
    handler_id = logger.add(lambda msg: records.append(msg.record), level="DEBUG")
    yield records
    logger.remove(handler_id)


@pytest.fixture
def simple_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The height of the Roman Empire under Augustus.",
        key_persons=[{"name": "Augustus", "role": "Emperor", "description": "First Roman Emperor"}],
        key_events=[{"name": "Battle of Actium", "date": "31 BC", "description": "Decisive naval battle"}],
        locations=[{"name": "Forum Romanum", "type": "plaza", "description": "The political heart of Rome"}],
        traditions=["gladiatorial games", "sacrifices to Jupiter"],
        technologies=["aqueducts", "concrete construction"],
        social_structure="Strict hierarchy: senators, equites, plebs, slaves",
    )


@pytest.fixture
def empty_graph() -> KnowledgeGraph:
    return KnowledgeGraph()


@pytest.fixture
def populated_graph(simple_setting) -> KnowledgeGraph:
    kg = KnowledgeGraph()
    kg.add_node(
        KnowledgeNode(
            text="Rome is the capital of the empire.",
            scope=KnowledgeScope.WORLD,
            source=KnowledgeSource.FACT,
            tags=["setting", "overview"],
        )
    )
    kg.add_node(
        KnowledgeNode(
            text="Whispers of a conspiracy in the Senate.",
            scope=KnowledgeScope.CITY,
            source=KnowledgeSource.RUMOR,
            tags=["politics"],
        )
    )
    kg.add_node(
        KnowledgeNode(
            text="The market on the Via Sacra sells fine silks.",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.FACT,
            tags=["trade"],
        )
    )
    return kg


@pytest.fixture
def game_state(simple_setting, populated_graph) -> GameState:
    return GameState(setting=simple_setting, knowledge_graph=populated_graph)


@pytest.fixture
def sample_npc() -> NPCCard:
    return NPCCard(
        name="Marcus",
        biography="A weathered Roman legionary.",
        occupation="Soldier",
        personality_traits=["brave", "loyal"],
        speech_style="blunt",
        attributes={"education": 3, "social_status": 4, "strength": 8},
        inventory=["gladius", "scutum"],
        location_id=None,
    )


@pytest.fixture
def sample_location() -> Location:
    return Location(
        name="Forum Romanum",
        description="The political heart of ancient Rome.",
        location_type="plaza",
        tags=["public", "political"],
    )
