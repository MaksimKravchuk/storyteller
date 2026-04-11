"""Tests for cast.data_miner.DataMiner — two-step research flow and Wikipedia fan-out."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast.data_miner import DataMiner
from models.setting import Setting
from research.wikipedia_client import WikipediaClient

_SEND_JSON = "_send_json"


def _default_summary() -> dict:
    return {"title": "T", "extract": "E", "description": "D"}


def _fake_wiki(summaries: list[dict] | None = None) -> MagicMock:
    wiki = MagicMock(spec=WikipediaClient)
    payloads = summaries or [_default_summary(), _default_summary()]
    wiki.get_summary = AsyncMock(side_effect=payloads)
    return wiki


def _full_setting_payload() -> dict:
    return {
        "name": "Florence",
        "time_period": "1480s",
        "region": "Tuscany",
        "summary": "The cradle of the Renaissance.",
        "key_persons": [{"name": "Lorenzo", "role": "ruler"}],
        "key_events": [{"name": "Pazzi conspiracy"}],
        "locations": [{"name": "Palazzo"}],
        "traditions": ["patronage"],
        "technologies": ["movable type"],
        "social_structure": "merchant republic",
    }


@allure.epic("World Setup")
@allure.feature("Data Miner")
class TestDataMiner:
    @allure.story("Construction")
    @allure.title("DataMiner creates a default WikipediaClient when none is injected")
    def test_default_wikipedia_client(self) -> None:
        miner = DataMiner(llm_client=MagicMock())
        assert isinstance(miner.wikipedia, WikipediaClient)

    @allure.story("Construction")
    @allure.title("DataMiner uses the injected wikipedia_client instead of creating a default")
    def test_injected_wikipedia_client(self) -> None:
        stub = _fake_wiki()
        miner = DataMiner(llm_client=MagicMock(), wikipedia_client=stub)
        assert miner.wikipedia is stub

    @allure.story("Research flow")
    @allure.title("DataMiner runs the two-step research flow and produces a populated Setting from LLM output")
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        miner = DataMiner(llm_client=MagicMock(), wikipedia_client=_fake_wiki())
        responses = [{"search_terms": ["Florence", "Medici"]}, _full_setting_payload()]
        with patch.object(miner, _SEND_JSON, new=AsyncMock(side_effect=responses)) as send_mock:
            result = await miner.act("Renaissance Florence", {})
        assert isinstance(result, Setting)
        assert result.name == "Florence"
        assert result.time_period == "1480s"
        assert result.region == "Tuscany"
        assert result.social_structure == "merchant republic"
        assert result.raw_sources == ["Florence", "Medici"]
        assert send_mock.call_count == 2

    @allure.story("Research flow")
    @allure.title("DataMiner defaults every missing key in the second LLM response to an empty value")
    @pytest.mark.asyncio
    async def test_defaults_when_fields_missing(self) -> None:
        miner = DataMiner(llm_client=MagicMock(), wikipedia_client=_fake_wiki([_default_summary()]))
        responses = [{"search_terms": ["Rome"]}, {}]
        with patch.object(miner, _SEND_JSON, new=AsyncMock(side_effect=responses)):
            result = await miner.act("Rome", {})
        assert result.name == "Unknown"
        assert result.time_period == ""
        assert result.region == ""
        assert result.summary == ""
        assert result.social_structure == ""
        assert result.key_persons == []
        assert result.traditions == []

    @allure.story("Research flow")
    @allure.title("DataMiner coerces null list fields in the LLM response to empty lists rather than leaving None")
    @pytest.mark.asyncio
    async def test_none_list_fields_become_empty(self) -> None:
        miner = DataMiner(llm_client=MagicMock(), wikipedia_client=_fake_wiki([_default_summary()]))
        responses = [
            {"search_terms": ["Rome"]},
            {
                "name": "Rome",
                "time_period": "1 AD",
                "region": "Italy",
                "summary": "x",
                "key_persons": None,
                "key_events": None,
                "locations": None,
                "traditions": None,
                "technologies": None,
            },
        ]
        with patch.object(miner, _SEND_JSON, new=AsyncMock(side_effect=responses)):
            result = await miner.act("Rome", {})
        assert result.key_persons == []
        assert result.key_events == []
        assert result.locations == []
        assert result.traditions == []
        assert result.technologies == []

    @allure.story("Search terms")
    @allure.title("DataMiner falls back to the raw input description when the LLM omits search_terms")
    @pytest.mark.asyncio
    async def test_search_terms_fallback(self) -> None:
        stub = _fake_wiki([_default_summary()])
        miner = DataMiner(llm_client=MagicMock(), wikipedia_client=stub)
        responses = [{}, _full_setting_payload()]
        with patch.object(miner, _SEND_JSON, new=AsyncMock(side_effect=responses)):
            await miner.act("Ancient Carthage", {})
        stub.get_summary.assert_awaited_once_with("Ancient Carthage")

    @allure.story("Concurrent fetch")
    @allure.title("DataMiner fetches one Wikipedia summary per returned search term concurrently")
    @pytest.mark.asyncio
    async def test_concurrent_fetch_count(self) -> None:
        stub = _fake_wiki([_default_summary(), _default_summary(), _default_summary()])
        miner = DataMiner(llm_client=MagicMock(), wikipedia_client=stub)
        responses = [{"search_terms": ["a", "b", "c"]}, _full_setting_payload()]
        with patch.object(miner, _SEND_JSON, new=AsyncMock(side_effect=responses)):
            result = await miner.act("multi", {})
        assert stub.get_summary.await_count == 3
        assert result.raw_sources == ["a", "b", "c"]
