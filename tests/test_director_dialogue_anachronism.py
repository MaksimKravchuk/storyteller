"""Anachronism classifier wiring in the Director's dialogue path (consumer-side seams)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from cast import director_dialogue as dlg_mod
from cast.schemas.anachronism import AnachronismAssessment
from knowledge import salience as salience_presets
from knowledge.memory import MemoryManager
from knowledge.query import KnowledgeQueryEngine
from llm.message import LLMResponse
from models.scene import Scene, SceneNPC
from tests.director_helpers import make_game_state, make_mock_actor, make_uuid, setup_npc

_NPC = make_uuid("npc-marcus")
_FORUM = make_uuid("forum")
_PLAYER_LINE = "I take a photo of you with my smartphone"
_REWRITE = "The stranger holds up a glowing slate and stares at you"


def _handler(classifier: object | None, era: str = "modern day"):
    gs = make_game_state()
    gs.player.origin_era = era
    setup_npc(gs, _NPC, name="Marcus", occupation="legionary")
    gs.knowledge_graph.register_actor_node(_NPC, label="Marcus (legionary)")
    gs.current_scene = Scene(
        location_id=_FORUM,
        description="The Forum.",
        npcs_present=[SceneNPC(role="legionary", uuid=_NPC)],
    )
    actor = make_mock_actor("Hail.")
    llm = AsyncMock()
    llm.send_message = AsyncMock(return_value=LLMResponse(body="Marcus is wary.", model="stub", usage={}))
    manager = MemoryManager(graph=gs.knowledge_graph, llm_client=llm)
    return gs, actor, dlg_mod.DialogueHandler(gs, {_NPC: actor}, manager, classifier)


def _classifier(assessment: AnachronismAssessment) -> MagicMock:
    classifier = MagicMock()
    classifier.act = AsyncMock(return_value=assessment)
    return classifier


@allure.epic("Narrative Delivery")
@allure.feature("Anachronism classifier")
@allure.story("Dialogue wiring")
class TestDialogueAnachronism:
    @allure.title("A strange line reaches the Actor as its perceived rewrite, not the raw text")
    @pytest.mark.asyncio
    async def test_actor_receives_perceived_rewrite(self):
        classifier = _classifier(
            AnachronismAssessment(strangeness_score=8, unfamiliar_concepts=["smartphone"], perceived_rewrite=_REWRITE),
        )
        _, actor, handler = _handler(classifier)

        await handler.handle_dialogue(_PLAYER_LINE, ["Marcus"])

        sent = actor.execute.call_args.kwargs["input_data"]
        assert _REWRITE in sent
        assert "smartphone" not in sent

    @allure.title("A strange line leaves an ANACHRONISM_ENCOUNTER memory tagged with the concept on the addressed NPC")
    @pytest.mark.asyncio
    async def test_encounter_memory_written(self):
        classifier = _classifier(
            AnachronismAssessment(strangeness_score=8, unfamiliar_concepts=["smartphone"], perceived_rewrite=_REWRITE),
        )
        gs, _, handler = _handler(classifier)

        await handler.handle_dialogue(_PLAYER_LINE, ["Marcus"])

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_held_by(_NPC)
        encounter = [m for m in memories if "smartphone" in m.tags]
        assert len(encounter) == 1
        assert encounter[0].salience == salience_presets.ANACHRONISM_ENCOUNTER

    @allure.title("A low strangeness score leaves the action and memories untouched")
    @pytest.mark.asyncio
    async def test_ordinary_line_unchanged(self):
        classifier = _classifier(AnachronismAssessment(strangeness_score=1, perceived_rewrite=_REWRITE))
        gs, actor, handler = _handler(classifier)

        await handler.handle_dialogue("greetings", ["Marcus"])

        assert _REWRITE not in actor.execute.call_args.kwargs["input_data"]
        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_held_by(_NPC)
        assert all(m.salience != salience_presets.ANACHRONISM_ENCOUNTER for m in memories)

    @allure.title("A classifier failure does not break the dialogue turn")
    @pytest.mark.asyncio
    async def test_classifier_failure_is_swallowed(self):
        classifier = MagicMock()
        classifier.act = AsyncMock(side_effect=RuntimeError("boom"))
        _, actor, handler = _handler(classifier)

        entries, _ = await handler.handle_dialogue("greetings", ["Marcus"])

        assert len(entries) == 1
        assert "greetings" in actor.execute.call_args.kwargs["input_data"]

    @allure.title("Without a classifier the dialogue path behaves as before")
    @pytest.mark.asyncio
    async def test_no_classifier(self):
        _, actor, handler = _handler(None)

        await handler.handle_dialogue("greetings", ["Marcus"])

        assert "greetings" in actor.execute.call_args.kwargs["input_data"]
