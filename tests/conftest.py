"""Shared pytest fixtures."""

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
