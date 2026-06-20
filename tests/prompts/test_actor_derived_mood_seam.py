"""Consumer-seam contract: the derived mood reaches the Actor prompt body (EN + RU).

The emotional deriver is the *supplier*; the Actor prompt is the
*consumer*. Per ADR-0002 this asserts the deterministically derived mood
value actually reaches the rendered system prompt sent to the LLM — in
both locales — not merely that ``derive_mood`` returns it. Option A: the
mood rides the existing ``current_mood`` prompt var (no new section).
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import allure
import pytest

from cast import actor as actor_mod, director_dialogue, emotional_memory as em
from cast.hostility import _MOOD_INTENSITY
from knowledge import charge
from knowledge.node import CanonSource, EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from knowledge.query import KnowledgeQueryEngine
from tests.prompts import _consumer_seam_kwargs as kwargs_mod, _consumer_seam_state as state_mod

pytestmark = [
    allure.epic("NPC Interaction"),
    allure.feature("Emotional memory"),
    allure.story("Derived mood reaches prose"),
]


def _charge_guard(game_state) -> None:
    """Stamp several strong witnessed-violence memories so the guard derives a hostile mood."""
    graph = game_state.knowledge_graph
    for _ in range(5):
        node_id = graph.add_node(
            KnowledgeNode(
                text="a brutal clash",
                scope=KnowledgeScope.LOCAL,
                source=KnowledgeSource.PERSONAL_EXPERIENCE,
                canon=CanonSource.SESSION,
                salience=0.9,
                valence=charge.COMBAT.base_valence,
                charge_intensity=0.9,
                charge_category=charge.VIOLENCE,
                subject_id=uuid4(),
                timestamp=game_state.game_clock,
            ),
        )
        graph.register_actor_node(state_mod.NPC_GUARD_ID)
        graph.add_edge(state_mod.NPC_GUARD_ID, node_id, EdgeType.WITNESSED)


@pytest.mark.parametrize("language", ["English", "Russian"])
@pytest.mark.asyncio
@allure.title("The derived mood appears verbatim in the rendered Actor prompt (EN + RU)")
async def test_derived_mood_reaches_rendered_prompt(language: str) -> None:
    game_state = state_mod.build_maximal_game_state()
    guard = game_state.npcs[state_mod.NPC_GUARD_ID]
    _charge_guard(game_state)
    expected_mood = em.derive_mood(
        guard,
        game_state.knowledge_graph.personal_memories_for(guard.uuid),
        game_state.game_clock,
    )
    assert _MOOD_INTENSITY[expected_mood] >= _MOOD_INTENSITY["angry"]  # the charge is strong

    client = AsyncMock()
    client.send_message.return_value.body = kwargs_mod.ACTOR_REPLY_JSON
    actor = actor_mod.Actor(
        llm_client=client,
        npc=guard,
        knowledge_query=KnowledgeQueryEngine(game_state.knowledge_graph),
        language=language,
    )

    # Drive the real dialogue-orchestration seam: it derives the mood, writes
    # it onto the NPC, then renders the Actor prompt.
    await director_dialogue._execute_npc_dialogue(guard, actor, "What are you doing here?", None, game_state)

    system_prompt = client.send_message.call_args.kwargs["system_prompt"]
    assert expected_mood in system_prompt  # the derived mood reached the prompt body
    assert guard.current_mood == expected_mood  # and was written through the seam
