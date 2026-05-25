"""Real-model DataMiner smoke tests.

The DataMiner runs a two-stage pipeline: ask the LLM for search terms,
then fetch Wikipedia summaries and synthesise a structured
:class:`models.setting.Setting`. We mock the :class:`WikipediaClient` so
the test is deterministic on the upstream half and stays isolated from
network flakiness, but the LLM half is real. The mocked summary plants a
distinctive proper name (``Lorenzo de' Medici``) that must surface in
the final ``Setting`` — that is the input-tied assertion.
"""

from __future__ import annotations

from unittest import mock

import allure
import pytest

from cast.data_miner import DataMiner
from models.setting import Setting
from research.wikipedia_client import WikipediaClient
from tests.e2e._real_llm import real_llm_for

_DISTINCTIVE_NAME = "Lorenzo de' Medici"
_FLORENCE_SUMMARY = (
    "Florence in the 1480s was the cultural and political centre of the Italian Renaissance. "
    "Under Lorenzo de' Medici, the city flourished as a hub of art, banking and humanist scholarship."
)
_MEDICI_SUMMARY = (
    "Lorenzo de' Medici (1449-1492), called Il Magnifico, was the de facto ruler of the Florentine "
    "Republic during the Italian Renaissance and a noted patron of Botticelli and Michelangelo."
)


async def _fake_get_summary(term: str) -> dict[str, str]:
    """Return a canned Florence/Medici summary keyed by case-insensitive substring.

    Unmatched terms (e.g. "Guelphs and Ghibellines", which the LLM
    legitimately picks alongside the primary entities) get an empty
    placeholder rather than an exception — the test's loud-failure
    signal lives in the call-args assertion of
    ``test_real_model_surfaces_wikipedia_fact``, which proves at least
    one Florence/Medici/Lorenzo term hit the mock.
    """
    lower = term.lower()
    if "medici" in lower or "lorenzo" in lower:
        return {"title": _DISTINCTIVE_NAME, "summary": _MEDICI_SUMMARY}
    if "florence" in lower or "florentine" in lower or "italy" in lower or "renaissance" in lower:
        return {"title": "Florence", "summary": _FLORENCE_SUMMARY}
    return {"title": term, "summary": "(no detail available)"}


def _mock_wikipedia_with_florence() -> mock.AsyncMock:
    """Build a WikipediaClient mock backed by :func:`_fake_get_summary`.

    ``DataMiner._extract_search_terms`` asks the LLM what to search for,
    so we cannot know the exact term keys at fixture time. The substring
    routing in ``_fake_get_summary`` keeps the test robust to the LLM's
    choice of phrasing.
    """
    wiki = mock.AsyncMock(spec=WikipediaClient)
    wiki.get_summary = mock.AsyncMock(side_effect=_fake_get_summary)
    return wiki


@allure.epic("AI Agent Orchestration")
@allure.feature("DataMiner real-model setting synthesis")
class TestDataMinerRealModel:
    @allure.story("Distinctive Wikipedia fact survives synthesis")
    @allure.title("A real DataMiner model surfaces a mocked Wikipedia fact in the final Setting")
    @pytest.mark.asyncio
    async def test_real_model_surfaces_wikipedia_fact(self):
        wiki = _mock_wikipedia_with_florence()
        miner = DataMiner(
            llm_client=real_llm_for("data_miner"),
            wikipedia_client=wiki,
            language="English",
        )

        setting = await miner.act("Medieval Florence in the 1480s during Lorenzo de Medici's rule.")

        # Independent proof the DataMiner actually consulted the mock
        # for a Lorenzo-bearing term — pins the failure mode "research
        # call skipped entirely" to a distinct assertion from the
        # downstream haystack check.
        called_terms = [call.args[0].lower() for call in wiki.get_summary.call_args_list]
        assert any("lorenzo" in term or "medici" in term or "florence" in term for term in called_terms), (
            "DataMiner did not query Wikipedia for any Florence/Medici/Lorenzo term; called: {0}".format(
                called_terms,
            )
        )

        assert isinstance(setting, Setting)
        assert setting.name.strip(), "Setting has empty name"
        assert setting.summary.strip(), "Setting has empty summary"
        # Input-tied: the distinctive Wikipedia name must surface
        # somewhere in the synthesised setting (summary, key_persons,
        # or social_structure). Failure mode this catches: the
        # ``raw_research`` JSON dropped from the second-stage prompt,
        # so the model would synthesise from its own prior on Florence
        # without using the supplied facts.
        person_names = " ".join(person.get("name", "") for person in setting.key_persons)
        haystack = " ".join((setting.summary, person_names, setting.social_structure)).lower()
        assert "lorenzo" in haystack or "medici" in haystack, (
            "Setting did not surface the mocked Wikipedia fact 'Lorenzo de Medici'.\n"
            "summary={0!r}\nkey_persons={1!r}".format(setting.summary, setting.key_persons)
        )

    @allure.story("Structural schema contract")
    @allure.title("A real DataMiner returns a structurally valid Setting on a thin request")
    @pytest.mark.asyncio
    async def test_real_model_returns_structurally_valid_setting(self):
        miner = DataMiner(
            llm_client=real_llm_for("data_miner"),
            wikipedia_client=_mock_wikipedia_with_florence(),
            language="English",
        )

        setting = await miner.act("Renaissance Florence.")

        assert isinstance(setting, Setting)
        assert setting.name.strip()
        assert setting.time_period.strip()
        assert setting.region.strip()
        assert setting.summary.strip()
        assert isinstance(setting.key_persons, list)
        assert isinstance(setting.key_events, list)
        assert isinstance(setting.locations, list)
