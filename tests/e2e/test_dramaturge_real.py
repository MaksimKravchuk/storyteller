"""Real-model Dramaturge smoke tests.

The Dramaturge is the optional consistency oracle that reads the
Narrator's prose and either returns it unchanged or rewrites lines that
contradict canon. We do not assert that a planted contradiction *gets*
caught — that requires multi-judge consensus (Part B's rubric layer).
Here we assert the integration contract: a real LLM call succeeds, the
return type is a non-empty string, and an obvious contradiction does
not cause the path to raise (the documented fallback is "return the
original narration").
"""

from __future__ import annotations

import allure
import pytest

from cast.dramaturge import Dramaturge
from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource
from tests import director_helpers
from tests.e2e._real_llm import real_llm_for

_INNOCUOUS_NARRATION = (
    "The morning light slants through the colonnade. A street vendor calls out, "
    "advertising fresh bread, and the smell mingles with the dust kicked up by passing carts."
)
_CONTRADICTORY_NARRATION = (
    "Augustus strides through the Forum, his cloak billowing as he greets the senators. "
    "His voice is strong and untroubled by his recent death."
)


@allure.epic("AI Agent Orchestration")
@allure.feature("Dramaturge real-model consistency oracle")
class TestDramaturgeRealModel:
    @allure.story("Innocuous narration round-trips")
    @allure.title("A real Dramaturge model returns innocuous narration as a non-empty string")
    @pytest.mark.asyncio
    async def test_real_model_returns_string_for_innocuous_narration(self):
        game_state = director_helpers.make_game_state()
        dramaturge = Dramaturge(llm_client=real_llm_for("dramaturge"), language="English")

        result = await dramaturge.act(_INNOCUOUS_NARRATION, {"game_state": game_state})

        assert isinstance(result, str)
        assert result.strip(), "Dramaturge returned empty narration"
        # Input-tied: an innocuous passage has nothing for the
        # consistency oracle to rewrite, so the returned text either
        # equals the input or contains the input's distinctive nouns.
        # Failure mode this catches: the oracle silently dropping the
        # input on the floor and emitting unrelated prose.
        lower = result.lower()
        assert "vendor" in lower or "bread" in lower or "colonnade" in lower, (
            "Dramaturge output did not preserve any input noun.\nResult was:\n{0}".format(result)
        )

    @allure.story("Contradiction path does not crash")
    @allure.title("A real Dramaturge handles a planted canon contradiction without raising")
    @pytest.mark.asyncio
    async def test_real_model_handles_contradiction_without_raising(self):
        game_state = director_helpers.make_game_state()
        # Plant the historical fact the narration contradicts.
        game_state.knowledge_graph.add_node(
            KnowledgeNode(
                text="Augustus died in 14 AD.",
                scope=KnowledgeScope.WORLD,
                source=KnowledgeSource.FACT,
                tags=["augustus", "history"],
            ),
        )
        dramaturge = Dramaturge(llm_client=real_llm_for("dramaturge"), language="English")

        result = await dramaturge.act(_CONTRADICTORY_NARRATION, {"game_state": game_state})

        # Documented behaviour: either the original narration is
        # returned (oracle declined to rewrite) or a rewritten string is
        # produced. Both are valid; what we guard against is the path
        # raising and the "player must never see a half-rewritten
        # passage" invariant being violated.
        assert isinstance(result, str)
        assert result.strip(), "Dramaturge returned empty narration on the contradiction path"
