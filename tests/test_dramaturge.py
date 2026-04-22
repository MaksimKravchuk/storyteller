"""Tests for the Dramaturge consistency oracle.

Covers the performer itself — prompt assembly from historical canon and
scene conversation log, rewrite of a contradicting sentence, passthrough
of clean narration, escalation of unknown-entity hints to
``DataMiner.ensure_fact``, and the session-canon guardrail (nodes with
``CanonSource.SESSION`` must never surface in the historical-canon
section of the prompt, because the Dramaturge is forbidden from
rewriting the player's own in-session truth).

PlanExecutor wiring lives in ``test_director_dramaturge.py`` alongside
the World Chronicler wiring tests, so that file stays beneath the
per-module import budget.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.dramaturge import (
    Dramaturge,
    _EMPTY_FACTS_PLACEHOLDER,
    _EMPTY_HISTORY_PLACEHOLDER,
    _format_historical_facts,
    _format_scene_history,
)
from cast.schemas.dramaturge_response import DramaturgeResponse
from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models.game_state import GameState
from models.scene import Scene, SceneNPC
from models.setting import Setting

_PLAYER_ACTION = "player_action"
_GAME_STATE = "game_state"
_DATA_MINER = "data_miner"


def _make_game_state() -> GameState:
    setting = Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The Roman Empire under the early emperors.",
    )
    gs = GameState(setting=setting, knowledge_graph=KnowledgeGraph())
    gs.current_scene = Scene(
        location_id="forum",
        description="The Roman Forum at noon.",
        npcs_present=[SceneNPC(role="guard", uuid="npc-1")],
    )
    return gs


def _add_historical_fact(gs: GameState, text: str, tags: list[str] | None = None) -> None:
    gs.knowledge_graph.add_node(
        KnowledgeNode(
            text=text,
            scope=KnowledgeScope.WORLD,
            source=KnowledgeSource.FACT,
            canon=CanonSource.HISTORICAL,
            tags=tags or ["historical_fact"],
        ),
    )


def _add_session_fact(gs: GameState, text: str) -> None:
    gs.knowledge_graph.add_node(
        KnowledgeNode(
            text=text,
            scope=KnowledgeScope.WORLD,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            tags=["session_fact"],
        ),
    )


def _make_dramaturge(
    payload: DramaturgeResponse | Exception,
) -> Dramaturge:
    dram = Dramaturge(llm_client=AsyncMock(), language="English")
    if isinstance(payload, Exception):
        dram._send_json = AsyncMock(side_effect=payload)  # type: ignore[method-assign]
    else:
        dram._send_json = AsyncMock(return_value=payload)  # type: ignore[method-assign]
    return dram


@allure.epic("Narrative Delivery")
@allure.feature("Dramaturge")
class TestDramaturgeRewrites:
    @allure.story("Historical canon")
    @allure.title("Dramaturge rewrites a sentence that contradicts a historical fact")
    @pytest.mark.asyncio
    async def test_rewrites_anachronism_against_historical_canon(self):
        gs = _make_game_state()
        _add_historical_fact(
            gs,
            "Julius Caesar was assassinated on the Ides of March, 44 BC, in the Theatre of Pompey.",
        )
        dram = _make_dramaturge(
            DramaturgeResponse(
                corrected_narration=(
                    "You see **Julius Caesar** crossing the Forum, bound for the "
                    "Theatre of Pompey, where in 44 BC the senators will fall upon him."
                ),
                contradictions=["Caesar was shown with a pistol in the original passage"],
                unknown_entities=[],
            ),
        )

        corrected = await dram.act(
            input_data=(
                "You see **Julius Caesar** crossing the Forum, his pistol "
                "glinting as he heads for the Theatre of Pompey."
            ),
            context={_GAME_STATE: gs, _PLAYER_ACTION: "walk through the forum"},
        )

        assert "pistol" not in corrected
        assert "Theatre of Pompey" in corrected

    @allure.story("Session canon")
    @allure.title("Dramaturge rewrites a sentence that contradicts an earlier in-scene NPC statement")
    @pytest.mark.asyncio
    async def test_rewrites_contradicting_scene_dialogue(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {
                _PLAYER_ACTION: "ask the guard his name",
                "response_summary": "The guard says his name is Marcus Aurelius.",
                "action_type": "TALK",
            },
        ]
        dram = _make_dramaturge(
            DramaturgeResponse(
                corrected_narration="The guard, **Marcus**, nods silently at your approach.",
                contradictions=["Guard was called Julius after introducing himself as Marcus"],
                unknown_entities=[],
            ),
        )

        corrected = await dram.act(
            input_data="The guard, **Julius**, nods silently at your approach.",
            context={_GAME_STATE: gs, _PLAYER_ACTION: "approach the guard"},
        )

        assert "Marcus" in corrected
        assert "Julius" not in corrected

    @allure.story("Passthrough")
    @allure.title("Dramaturge passes clean narration through verbatim when no contradictions are reported")
    @pytest.mark.asyncio
    async def test_clean_narration_passes_through(self):
        gs = _make_game_state()
        clean = "The forum bustles with merchants and senators, the air thick with incense."
        dram = _make_dramaturge(
            DramaturgeResponse(corrected_narration=clean, contradictions=[], unknown_entities=[]),
        )

        result = await dram.act(
            input_data=clean,
            context={_GAME_STATE: gs, _PLAYER_ACTION: "look around"},
        )

        assert result == clean


@allure.epic("Narrative Delivery")
@allure.feature("Dramaturge")
class TestDramaturgePromptAssembly:
    @allure.story("Historical canon")
    @allure.title("System prompt includes historical-canon facts but omits session-canon facts")
    @pytest.mark.asyncio
    async def test_prompt_includes_historical_not_session_canon(self):
        gs = _make_game_state()
        _add_historical_fact(gs, "Rome is the capital of the empire and seat of the Senate.")
        _add_session_fact(gs, "The player has bribed the Praetorian guard this session.")

        dram = _make_dramaturge(
            DramaturgeResponse(corrected_narration="x", contradictions=[], unknown_entities=[]),
        )

        await dram.act(
            input_data="x",
            context={_GAME_STATE: gs, _PLAYER_ACTION: "look"},
        )

        system_prompt = dram.system_prompt_template.render(**dram._system_prompt_vars)
        assert "capital of the empire" in system_prompt
        assert "bribed the Praetorian" not in system_prompt

    @allure.story("Scene history")
    @allure.title("System prompt includes the tail of scene_conversation_log under the session-canon heading")
    @pytest.mark.asyncio
    async def test_prompt_includes_scene_conversation_log(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {
                _PLAYER_ACTION: "hail the guard",
                "response_summary": "The guard introduces himself as Marcus.",
                "action_type": "TALK",
            },
        ]
        dram = _make_dramaturge(
            DramaturgeResponse(corrected_narration="x", contradictions=[], unknown_entities=[]),
        )

        await dram.act(
            input_data="x",
            context={_GAME_STATE: gs, _PLAYER_ACTION: "approach"},
        )

        system_prompt = dram.system_prompt_template.render(**dram._system_prompt_vars)
        assert "introduces himself as Marcus" in system_prompt

    @allure.story("Empty narration")
    @allure.title("Dramaturge short-circuits on empty narration without calling the LLM")
    @pytest.mark.asyncio
    async def test_empty_narration_short_circuits(self):
        gs = _make_game_state()
        dram = _make_dramaturge(
            DramaturgeResponse(corrected_narration="", contradictions=[], unknown_entities=[]),
        )

        result = await dram.act(
            input_data="   ",
            context={_GAME_STATE: gs, _PLAYER_ACTION: "wait"},
        )

        assert result == ""
        dram._send_json.assert_not_called()  # type: ignore[attr-defined]

    @allure.story("Empty correction")
    @allure.title("Dramaturge falls back and skips escalation when corrected_narration is empty")
    @pytest.mark.asyncio
    async def test_empty_corrected_narration_falls_back_and_skips_escalation(self):
        gs = _make_game_state()
        data_miner = AsyncMock()
        data_miner.ensure_fact = AsyncMock()
        dram = _make_dramaturge(
            DramaturgeResponse(
                corrected_narration="   ",
                contradictions=[],
                unknown_entities=["Pantheon"],
            ),
        )
        original = "The sun glints off marble."

        result = await dram.act(
            input_data=original,
            context={_GAME_STATE: gs, _PLAYER_ACTION: "look", _DATA_MINER: data_miner},
        )

        assert result == original
        data_miner.ensure_fact.assert_not_awaited()


@allure.epic("Narrative Delivery")
@allure.feature("Dramaturge")
class TestDramaturgeEscalation:
    @allure.story("ensure_fact escalation")
    @allure.title("Dramaturge calls DataMiner.ensure_fact once per unknown_entities hint")
    @pytest.mark.asyncio
    async def test_escalates_unknowns_to_data_miner(self):
        gs = _make_game_state()
        data_miner = AsyncMock()
        data_miner.ensure_fact = AsyncMock(return_value=None)

        dram = _make_dramaturge(
            DramaturgeResponse(
                corrected_narration="You see the Pantheon on your right.",
                contradictions=[],
                unknown_entities=["Pantheon", "Colosseum"],
            ),
        )

        await dram.act(
            input_data="You see the ancient Pantheon on your right.",
            context={
                _GAME_STATE: gs,
                _PLAYER_ACTION: "walk",
                _DATA_MINER: data_miner,
            },
        )

        assert data_miner.ensure_fact.await_count == 2
        called_names = {call.args[0] for call in data_miner.ensure_fact.await_args_list}
        assert called_names == {"Pantheon", "Colosseum"}

    @allure.story("ensure_fact escalation")
    @allure.title("ensure_fact receives the game_state's own KnowledgeGraph instance")
    @pytest.mark.asyncio
    async def test_ensure_fact_called_with_game_state_graph(self):
        gs = _make_game_state()
        data_miner = AsyncMock()
        data_miner.ensure_fact = AsyncMock(return_value=None)
        dram = _make_dramaturge(
            DramaturgeResponse(
                corrected_narration="x",
                contradictions=[],
                unknown_entities=["Pantheon"],
            ),
        )

        await dram.act(
            input_data="x",
            context={_GAME_STATE: gs, _PLAYER_ACTION: "look", _DATA_MINER: data_miner},
        )

        call = data_miner.ensure_fact.await_args_list[0]
        assert call.kwargs["graph"] is gs.knowledge_graph

    @allure.story("ensure_fact escalation")
    @allure.title("Empty and whitespace-only entries are filtered before ensure_fact is called")
    @pytest.mark.asyncio
    async def test_clean_entity_hints_filters_whitespace(self):
        gs = _make_game_state()
        data_miner = AsyncMock()
        data_miner.ensure_fact = AsyncMock(return_value=None)
        dram = _make_dramaturge(
            DramaturgeResponse(
                corrected_narration="x",
                contradictions=[],
                unknown_entities=["Pantheon", "", "  ", "Colosseum"],
            ),
        )

        await dram.act(
            input_data="x",
            context={_GAME_STATE: gs, _PLAYER_ACTION: "look", _DATA_MINER: data_miner},
        )

        assert data_miner.ensure_fact.await_count == 2
        called = {call.args[0] for call in data_miner.ensure_fact.await_args_list}
        assert called == {"Pantheon", "Colosseum"}

    @allure.story("ensure_fact escalation")
    @allure.title("A failing ensure_fact lookup does not prevent other lookups from running")
    @pytest.mark.asyncio
    async def test_partial_failure_does_not_break_other_lookups(self):
        gs = _make_game_state()
        data_miner = AsyncMock()
        data_miner.ensure_fact = AsyncMock(
            side_effect=[RuntimeError("wiki 404"), None, RuntimeError("network down")],
        )
        dram = _make_dramaturge(
            DramaturgeResponse(
                corrected_narration="You see three landmarks.",
                contradictions=[],
                unknown_entities=["Pantheon", "Colosseum", "Forum"],
            ),
        )

        result = await dram.act(
            input_data="You see three landmarks.",
            context={_GAME_STATE: gs, _PLAYER_ACTION: "look", _DATA_MINER: data_miner},
        )

        assert result == "You see three landmarks."
        assert data_miner.ensure_fact.await_count == 3
        called = {call.args[0] for call in data_miner.ensure_fact.await_args_list}
        assert called == {"Pantheon", "Colosseum", "Forum"}

    @allure.story("ensure_fact escalation")
    @allure.title("Dramaturge still returns corrected narration when every ensure_fact call raises")
    @pytest.mark.asyncio
    async def test_escalation_failure_does_not_break_rewrite(self):
        gs = _make_game_state()
        data_miner = AsyncMock()
        data_miner.ensure_fact = AsyncMock(side_effect=RuntimeError("wiki down"))

        dram = _make_dramaturge(
            DramaturgeResponse(
                corrected_narration="The forum is quiet.",
                contradictions=[],
                unknown_entities=["Unknown landmark"],
            ),
        )

        result = await dram.act(
            input_data="The forum is quiet with a glowing hologram in the sky.",
            context={
                _GAME_STATE: gs,
                _PLAYER_ACTION: "look",
                _DATA_MINER: data_miner,
            },
        )

        assert result == "The forum is quiet."

    @allure.story("Failure fallback")
    @allure.title("Dramaturge returns the original narration for any exception type the review raises")
    @pytest.mark.parametrize(
        "exc",
        [
            ValueError("bad json"),
            RuntimeError("boom"),
            KeyError("missing"),
            TypeError("nope"),
        ],
    )
    @pytest.mark.asyncio
    async def test_any_exception_type_falls_back_to_original(self, exc):
        gs = _make_game_state()
        original = "The sun glints off the marble columns."
        dram = _make_dramaturge(exc)

        result = await dram.act(
            input_data=original,
            context={_GAME_STATE: gs, _PLAYER_ACTION: "look"},
        )

        assert result == original


@allure.epic("Narrative Delivery")
@allure.feature("Dramaturge")
class TestDramaturgeHelpers:
    @allure.story("Prompt helpers")
    @allure.title("_format_historical_facts returns a placeholder when the graph has no historical nodes")
    def test_format_historical_facts_empty(self):
        graph = KnowledgeGraph()
        graph.add_node(
            KnowledgeNode(
                text="Session-only fact",
                canon=CanonSource.SESSION,
            ),
        )
        assert _format_historical_facts(graph) == _EMPTY_FACTS_PLACEHOLDER

    @allure.story("Prompt helpers")
    @allure.title("_format_historical_facts bullet-formats historical canon")
    def test_format_historical_facts_bullets(self):
        graph = KnowledgeGraph()
        graph.add_node(
            KnowledgeNode(
                text="Rome was founded in 753 BC.",
                canon=CanonSource.HISTORICAL,
                source=KnowledgeSource.FACT,
            ),
        )
        rendered = _format_historical_facts(graph)
        assert rendered.startswith("- ")
        assert "753 BC" in rendered

    @allure.story("Prompt helpers")
    @allure.title("_format_historical_facts caps output at _MAX_HISTORICAL_FACTS to bound prompt size")
    def test_format_historical_facts_caps_at_twenty(self):
        graph = KnowledgeGraph()
        for idx in range(25):
            graph.add_node(
                KnowledgeNode(
                    text="Fact number {0}.".format(idx),
                    canon=CanonSource.HISTORICAL,
                    source=KnowledgeSource.FACT,
                ),
            )
        rendered = _format_historical_facts(graph)
        # 20 bullets separated by 19 newlines
        assert rendered.count("\n") == 19
        assert "Fact number 0." in rendered
        assert "Fact number 24." not in rendered

    @allure.story("Prompt helpers")
    @allure.title("_format_scene_history returns a placeholder on an empty log")
    def test_format_scene_history_empty(self):
        assert _format_scene_history([]) == _EMPTY_HISTORY_PLACEHOLDER

    @allure.story("Prompt helpers")
    @allure.title("_format_scene_history renders player action and response summary as bullets")
    def test_format_scene_history_bullets(self):
        entries = [
            {
                _PLAYER_ACTION: "greet guard",
                "response_summary": "The guard nods.",
                "action_type": "TALK",
            },
        ]
        rendered = _format_scene_history(entries)
        assert "greet guard" in rendered
        assert "The guard nods." in rendered

    @allure.story("Prompt helpers")
    @allure.title("_format_scene_history caps at _MAX_SCENE_HISTORY most recent entries")
    def test_format_scene_history_caps_at_eight(self):
        entries = [
            {_PLAYER_ACTION: "act {0}".format(idx), "response_summary": "result {0}".format(idx)} for idx in range(12)
        ]
        rendered = _format_scene_history(entries)
        # 8 bullets separated by 7 newlines
        assert rendered.count("\n") == 7
        # Newest four retained
        assert "act 11" in rendered
        assert "act 4" in rendered
        # Oldest four dropped
        assert "act 3" not in rendered
        assert "act 0" not in rendered
