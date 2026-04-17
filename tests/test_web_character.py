"""Unit tests for ``interfaces.web.character.build_character_info``.

Builds a ``GameState`` covering each ``CharacterInfo`` field and asserts
the builder projects NPCs from ``known_npcs``, recent events from
``player_event_log``, and facts from ``learned_facts`` through the
knowledge graph.
"""

from __future__ import annotations

import allure

from interfaces.web.character import build_character_info
from knowledge.node import (
    CanonSource,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from models.game_state import GameState
from models.npc_card import NPCCard

_STORY_BUILDER = "Character info builder"
_FACT_TEXT = "You smashed the clay amphora on the tavern floor."

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]


def _add_known_npc(game_state: GameState) -> NPCCard:
    npc = NPCCard(name="Marcus", occupation="legionary", short_descriptor="a stern soldier")
    game_state.npcs[npc.uuid] = npc
    game_state.player.known_npcs.add(npc.uuid)
    return npc


def _add_learned_fact(game_state: GameState, text: str) -> str:
    node = KnowledgeNode(
        text=text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
    )
    fact_uuid = game_state.knowledge_graph.add_node(node)
    game_state.player.learned_facts.add(fact_uuid)
    return fact_uuid


@allure.story(_STORY_BUILDER)
@allure.title("build_character_info projects the player identity and inventory fields")
def test_builder_projects_identity(game_state: GameState) -> None:
    game_state.player.name = "Aurelia"
    game_state.player.appearance = "A weathered traveller."
    game_state.player.inventory = ["waterskin", "letter of passage"]

    sidebar = build_character_info(game_state)

    assert sidebar.name == "Aurelia"
    assert sidebar.appearance == "A weathered traveller."
    assert sidebar.physical_status == "healthy"
    assert sidebar.inventory == ["waterskin", "letter of passage"]


@allure.story(_STORY_BUILDER)
@allure.title("build_character_info projects known NPCs as name/occupation/descriptor rows")
def test_builder_projects_known_npcs(game_state: GameState) -> None:
    _add_known_npc(game_state)

    known = build_character_info(game_state).known_npcs

    assert len(known) == 1
    assert known[0].name == "Marcus"
    assert known[0].occupation == "legionary"
    assert known[0].descriptor == "a stern soldier"


@allure.story(_STORY_BUILDER)
@allure.title("build_character_info projects player_event_log verbatim into recent_events")
def test_builder_projects_recent_events(game_state: GameState) -> None:
    game_state.player.player_event_log.append("Met Marcus (legionary)")

    sidebar = build_character_info(game_state)

    assert sidebar.recent_events == ["Met Marcus (legionary)"]


@allure.story(_STORY_BUILDER)
@allure.title("build_character_info projects learned_facts UUIDs into RememberedFact rows")
def test_builder_projects_learned_facts(game_state: GameState) -> None:
    _add_learned_fact(game_state, _FACT_TEXT)

    facts = build_character_info(game_state).learned_facts

    assert len(facts) == 1
    assert facts[0].text == _FACT_TEXT
    assert facts[0].source == "PERSONAL_EXPERIENCE"


@allure.story(_STORY_BUILDER)
@allure.title("build_character_info skips known_npcs UUIDs that no longer resolve to a card")
def test_builder_skips_evicted_npcs(game_state: GameState) -> None:
    game_state.player.known_npcs.add("ghost-uuid-not-in-npcs")

    assert build_character_info(game_state).known_npcs == []


@allure.story(_STORY_BUILDER)
@allure.title("build_character_info skips learned_facts UUIDs that no longer resolve to a graph node")
def test_builder_skips_missing_facts(game_state: GameState) -> None:
    game_state.player.learned_facts.add("ghost-uuid-not-in-graph")

    assert build_character_info(game_state).learned_facts == []


@allure.story(_STORY_BUILDER)
@allure.title("build_character_info sorts known_npcs and learned_facts by UUID for a stable payload")
def test_builder_sorts_set_backed_fields_by_uuid(game_state: GameState) -> None:
    first = NPCCard(name="Aulus", occupation="baker", short_descriptor="a flour-dusted baker")
    first.uuid = "npc-aaa"
    second = NPCCard(name="Brutus", occupation="guard", short_descriptor="a stern guard")
    second.uuid = "npc-bbb"
    game_state.npcs[first.uuid] = first
    game_state.npcs[second.uuid] = second
    game_state.player.known_npcs.update({second.uuid, first.uuid})

    alpha = KnowledgeNode(text="bread is fresh", source=KnowledgeSource.FACT)
    alpha.uuid = "fact-aaa"
    beta = KnowledgeNode(text="gates close at dusk", source=KnowledgeSource.FACT)
    beta.uuid = "fact-bbb"
    game_state.knowledge_graph.add_node(alpha)
    game_state.knowledge_graph.add_node(beta)
    game_state.player.learned_facts.update({beta.uuid, alpha.uuid})

    sidebar = build_character_info(game_state)

    assert [npc.name for npc in sidebar.known_npcs] == ["Aulus", "Brutus"]
    assert [fact.text for fact in sidebar.learned_facts] == ["bread is fresh", "gates close at dusk"]


@allure.story(_STORY_BUILDER)
@allure.title("build_character_info returns an empty payload for a fresh GameState")
def test_builder_handles_empty_state(game_state: GameState) -> None:
    sidebar = build_character_info(game_state)

    assert sidebar.name == "Player"
    assert sidebar.known_npcs == []
    assert sidebar.recent_events == []
    assert sidebar.learned_facts == []
