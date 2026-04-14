"""Tests for the Narrative Test Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.narrative_test_agent import NarrativeTestAgent
from cast.narrative_test_formatters import (
    build_audit_kwargs,
    format_current_scene,
    format_log,
    format_npc_memory,
    format_npc_profiles,
    format_recent_turns,
    format_world_threads,
)
from cast.schemas.narrative_test_response import (
    DimensionScore,
    NarrativeEvaluation,
)
from knowledge.graph import KnowledgeGraph
from models import game_state as gs_mod, npc_card as npc_mod, scene as scene_mod
from models import setting as setting_mod, world_state as ws_mod

_EMPTY = "(none)"


def _make_game_state() -> gs_mod.GameState:
    setting = setting_mod.Setting(
        name="Florence",
        time_period="1480s",
        region="Tuscany",
        summary="A merchant republic of painters, bankers, and assassins.",
    )
    gs = gs_mod.GameState(setting=setting, knowledge_graph=KnowledgeGraph())
    gs.scene_number = 4
    gs.turn_count = 9
    gs.current_scene = scene_mod.Scene(
        location_id="piazza_signoria",
        description="The Piazza della Signoria at dusk.",
        npcs_present=[scene_mod.SceneNPC(role="guard", uuid="npc-1")],
        points_of_interest=["well", "gallows"],
        ambient_description="Distant bells and the scent of woodsmoke.",
    )
    gs.world_state.world_mood = "coiled, watchful"
    gs.world_state.threads.append(
        ws_mod.WorldThread(
            description="A Medici bodyguard has gone missing",
            category="political",
            introduced_scene=2,
        ),
    )
    gs.conversation_log.extend(
        [
            {
                "turn": 8,
                "scene_number": 4,
                "player_action": "question the guard about the missing bodyguard",
                "response": "The guard stiffens and waves you off with a curt warning.",
                "game_clock": 17.5,
            },
            {
                "turn": 9,
                "scene_number": 4,
                "player_action": "push past him toward the palace gate",
                "response": "You shove; the guard grips your wrist and raises his halberd.",
                "game_clock": 17.6,
            },
        ],
    )
    npc = npc_mod.NPCCard(
        name="Guard",
        biography="A Medici house guard with ten years on the gate.",
        appearance="Tall, scarred across the brow.",
        occupation="House guard",
        personality_traits=["wary", "loyal"],
        speech_style="clipped",
        attributes={"strength": 7},
        inventory=["halberd"],
        location_id="piazza_signoria",
    )
    npc.uuid = "npc-1"
    npc.current_mood = "suspicious"
    npc.conversation_history = [
        {"role": "player", "content": "question about missing bodyguard"},
        {"role": "npc", "content": "I know nothing, stranger — move along."},
    ]
    gs.npcs["npc-1"] = npc
    return gs


def _valid_evaluation_payload() -> dict:
    dim = {
        "score": 7,
        "strengths": ["Guard's wariness lands"],
        "weaknesses": ["Still no follow-up on the missing bodyguard"],
        "recommendations": ["Introduce a witness in the next scene"],
    }
    return {
        "story": dim,
        "turns": dim,
        "scenes": dim,
        "confrontation": dim,
        "memory": dim,
        "autonomy": dim,
        "overall_score": 7.0,
        "summary": "Solid setup; the missing bodyguard thread needs a follow-through.",
    }


def _make_agent(payload: dict | Exception) -> NarrativeTestAgent:
    llm_client = AsyncMock()
    agent = NarrativeTestAgent(llm_client=llm_client)
    if isinstance(payload, Exception):
        agent._send_json = AsyncMock(side_effect=payload)  # type: ignore[method-assign]
    else:
        agent._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=NarrativeEvaluation.model_validate(payload),
        )
    return agent


@allure.epic("Narrative Delivery")
@allure.feature("Narrative Test Agent")
class TestNarrativeTestAgentHappyPath:
    @allure.story("Happy path")
    @allure.title("Narrative Test Agent returns a validated NarrativeEvaluation with all six dimensions")
    @pytest.mark.asyncio
    async def test_returns_evaluation(self):
        agent = _make_agent(_valid_evaluation_payload())
        gs = _make_game_state()

        evaluation = await agent.act(input_data=gs, context={})

        assert isinstance(evaluation, NarrativeEvaluation)
        assert evaluation.overall_score == pytest.approx(7.0)
        assert evaluation.story.score == 7
        assert evaluation.turns.score == 7
        assert evaluation.scenes.score == 7
        assert evaluation.confrontation.score == 7
        assert evaluation.memory.score == 7
        assert evaluation.autonomy.score == 7

    @allure.story("Prompt assembly")
    @allure.title("Audit prompt includes scene number, turn count, and world mood from the game state")
    @pytest.mark.asyncio
    async def test_prompt_mentions_scene_and_turn_counts(self):
        agent = _make_agent(_valid_evaluation_payload())
        gs = _make_game_state()

        await agent.act(input_data=gs, context={})

        prompt = agent._send_json.call_args.args[0]  # type: ignore[attr-defined]
        assert "Scene number: 4" in prompt
        assert "Turn count: 9" in prompt
        assert "coiled, watchful" in prompt

    @allure.story("Prompt assembly")
    @allure.title("Audit prompt surfaces recent player turns with narrator replies")
    @pytest.mark.asyncio
    async def test_prompt_includes_recent_turns(self):
        agent = _make_agent(_valid_evaluation_payload())
        gs = _make_game_state()

        await agent.act(input_data=gs, context={})

        prompt = agent._send_json.call_args.args[0]  # type: ignore[attr-defined]
        assert "question the guard" in prompt
        assert "shove; the guard" in prompt

    @allure.story("Prompt assembly")
    @allure.title("Audit prompt includes the current scene description, atmosphere, and points of interest")
    @pytest.mark.asyncio
    async def test_prompt_includes_scene_details(self):
        agent = _make_agent(_valid_evaluation_payload())
        gs = _make_game_state()

        await agent.act(input_data=gs, context={})

        prompt = agent._send_json.call_args.args[0]  # type: ignore[attr-defined]
        assert "Piazza della Signoria" in prompt
        assert "woodsmoke" in prompt
        assert "gallows" in prompt

    @allure.story("Prompt assembly")
    @allure.title("Audit prompt includes world threads with their category and status")
    @pytest.mark.asyncio
    async def test_prompt_includes_world_threads(self):
        agent = _make_agent(_valid_evaluation_payload())
        gs = _make_game_state()

        await agent.act(input_data=gs, context={})

        prompt = agent._send_json.call_args.args[0]  # type: ignore[attr-defined]
        assert "missing bodyguard" in prompt
        assert "[political/open]" in prompt

    @allure.story("Prompt assembly")
    @allure.title("Audit prompt includes optional confrontation and autonomy logs from context")
    @pytest.mark.asyncio
    async def test_prompt_includes_context_logs(self):
        agent = _make_agent(_valid_evaluation_payload())
        gs = _make_game_state()

        await agent.act(
            input_data=gs,
            context={
                "confrontation_log": ["Guard wins contest 14 vs 9 — player grip slips"],
                "autonomy_log": ["Apprentice at forge departs for the market"],
            },
        )

        prompt = agent._send_json.call_args.args[0]  # type: ignore[attr-defined]
        assert "Guard wins contest" in prompt
        assert "Apprentice at forge departs" in prompt


@allure.epic("Narrative Delivery")
@allure.feature("Narrative Test Agent")
class TestNarrativeTestAgentEmptyState:
    @allure.story("Empty snapshot")
    @allure.title("Audit prompt renders placeholders when the game state has no turns, threads, or NPCs")
    @pytest.mark.asyncio
    async def test_empty_state_uses_placeholders(self):
        agent = _make_agent(_valid_evaluation_payload())
        setting = setting_mod.Setting(name="Nowhere", time_period="1900", region="—", summary="A blank slate.")
        gs = gs_mod.GameState(setting=setting, knowledge_graph=KnowledgeGraph())

        await agent.act(input_data=gs, context={})

        prompt = agent._send_json.call_args.args[0]  # type: ignore[attr-defined]
        assert "Recent player turns (oldest first):\n(none)" in prompt
        assert "Active world threads:\n(none)" in prompt
        assert "NPC roster:\n(none)" in prompt

    @allure.story("Retries exhausted")
    @allure.title("Narrative Test Agent surfaces ValueError when _send_json retries are exhausted")
    @pytest.mark.asyncio
    async def test_retries_exhausted_raises(self):
        agent = _make_agent(ValueError("Agent failed to produce valid JSON"))
        gs = _make_game_state()

        with pytest.raises(ValueError, match="valid JSON"):
            await agent.act(input_data=gs, context={})


@allure.epic("Narrative Delivery")
@allure.feature("Narrative Test Agent")
class TestNarrativeTestAgentHelpers:
    @allure.story("Prompt helpers")
    @allure.title("format_recent_turns returns the empty placeholder when there are no conversation entries")
    def test_format_recent_turns_empty(self):
        assert format_recent_turns([]) == _EMPTY

    @allure.story("Prompt helpers")
    @allure.title("format_recent_turns numbers turns starting at 1 and keeps player/narrator lines")
    def test_format_recent_turns_numbers(self):
        rendered = format_recent_turns(
            [
                {"player_action": "go east", "response": "You walk east."},
                {"player_action": "look", "response": "A wall stretches north."},
            ],
        )
        assert "1. Player: go east" in rendered
        assert "2. Player: look" in rendered
        assert "Narrator: You walk east." in rendered

    @allure.story("Prompt helpers")
    @allure.title("format_current_scene returns placeholder when the scene is unset")
    def test_format_current_scene_unset(self):
        gs = gs_mod.GameState(
            setting=setting_mod.Setting(name="X", time_period="Y", region="Z", summary="w"),
            knowledge_graph=KnowledgeGraph(),
        )
        assert format_current_scene(gs) == _EMPTY

    @allure.story("Prompt helpers")
    @allure.title("format_world_threads returns placeholder when no threads exist")
    def test_format_world_threads_empty(self):
        assert format_world_threads([]) == _EMPTY

    @allure.story("Prompt helpers")
    @allure.title("format_npc_profiles returns placeholder when the NPC roster is empty")
    def test_format_npc_profiles_empty(self):
        gs = gs_mod.GameState(
            setting=setting_mod.Setting(name="X", time_period="Y", region="Z", summary="w"),
            knowledge_graph=KnowledgeGraph(),
        )
        assert format_npc_profiles(gs) == _EMPTY

    @allure.story("Prompt helpers")
    @allure.title("format_npc_memory returns placeholder when every NPC has an empty history")
    def test_format_npc_memory_all_silent(self):
        gs = _make_game_state()
        for npc in gs.npcs.values():
            npc.conversation_history = []
        assert format_npc_memory(gs) == _EMPTY

    @allure.story("Prompt helpers")
    @allure.title("format_log returns placeholder for an empty list and bullets for non-empty input")
    def test_format_log_branches(self):
        assert format_log([]) == _EMPTY
        rendered = format_log(["hit 14", "miss 3"])
        assert "- hit 14" in rendered
        assert "- miss 3" in rendered

    @allure.story("Prompt helpers")
    @allure.title("build_audit_kwargs assembles every key required by the NARRATIVE_TEST_AUDIT template")
    def test_build_audit_kwargs_keys(self):
        gs = _make_game_state()
        kwargs = build_audit_kwargs(gs, {})
        expected_keys = {
            "scene_number",
            "turn_count",
            "world_mood",
            "recent_turns",
            "current_scene",
            "world_threads",
            "npc_profiles",
            "npc_memory",
            "confrontation_log",
            "autonomy_log",
        }
        assert set(kwargs.keys()) == expected_keys


@allure.epic("Narrative Delivery")
@allure.feature("Narrative Test Agent")
class TestNarrativeEvaluationSchema:
    @allure.story("Schema validation")
    @allure.title("DimensionScore rejects integer scores outside the 1-10 range")
    def test_dimension_score_range(self):
        with pytest.raises(ValueError):
            DimensionScore(score=11)
        with pytest.raises(ValueError):
            DimensionScore(score=0)

    @allure.story("Schema validation")
    @allure.title("NarrativeEvaluation requires all six dimension scores to be present")
    def test_narrative_evaluation_requires_all_dimensions(self):
        partial = {
            "story": {"score": 5},
            "turns": {"score": 5},
            "scenes": {"score": 5},
            "confrontation": {"score": 5},
            "memory": {"score": 5},
            "overall_score": 5.0,
            "summary": "incomplete",
        }
        with pytest.raises(ValueError):
            NarrativeEvaluation.model_validate(partial)

    @allure.story("Schema validation")
    @allure.title("NarrativeEvaluation clamps overall_score to the 1.0-10.0 range")
    def test_overall_score_range(self):
        payload = _valid_evaluation_payload()
        payload["overall_score"] = 12.5
        with pytest.raises(ValueError):
            NarrativeEvaluation.model_validate(payload)
