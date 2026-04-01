"""Data Miner — researches real-world information to create grounded settings."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from cast.base_performer_class import BasePerformer
from models.setting import Setting
from prompts.data_miner_prompts import (
    DATA_MINER_RESEARCH,
    DATA_MINER_SEARCH_TERMS,
    DATA_MINER_SYSTEM,
)
from research.wikipedia_client import WikipediaClient


class DataMiner(BasePerformer):
    """Researches historical / geographical data via Wikipedia and synthesises
    it into a structured ``Setting`` for the game.
    """

    def __init__(
        self,
        *,
        llm_client: Any,
        wikipedia_client: WikipediaClient | None = None,
    ):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=DATA_MINER_SYSTEM,
        )
        self.wikipedia = wikipedia_client or WikipediaClient()

    async def act(self, input_data: str, context: dict | None = None) -> Setting:
        """Research a topic and produce a structured Setting.

        ``input_data``: Natural language description of the desired setting,
        e.g. "Medieval Florence, 1480s, during the reign of Lorenzo de Medici".
        """
        # Step 1: Ask the LLM what to search for
        search_terms = await self._extract_search_terms(input_data)

        # Step 2: Fetch Wikipedia summaries concurrently
        summaries = await asyncio.gather(
            *(self.wikipedia.get_summary(term) for term in search_terms),
        )
        raw_articles: dict[str, dict] = dict(zip(search_terms, summaries))

        # Step 3: Synthesise into a Setting via LLM
        research_prompt = DATA_MINER_RESEARCH.render(
            setting_request=input_data,
            raw_research=json.dumps(raw_articles, indent=2, ensure_ascii=False),
        )
        setting_data = await self._send_json(research_prompt)

        # Build the Setting model
        return Setting(
            name=setting_data.get("name", "Unknown"),
            time_period=setting_data.get("time_period", ""),
            region=setting_data.get("region", ""),
            summary=setting_data.get("summary", ""),
            key_persons=setting_data.get("key_persons") or [],
            key_events=setting_data.get("key_events") or [],
            locations=setting_data.get("locations") or [],
            traditions=setting_data.get("traditions") or [],
            technologies=setting_data.get("technologies") or [],
            social_structure=setting_data.get("social_structure", ""),
            raw_sources=list(raw_articles.keys()),
        )

    async def _extract_search_terms(self, description: str) -> list[str]:
        """Ask the LLM to generate Wikipedia search terms."""
        prompt = DATA_MINER_SEARCH_TERMS.render(setting_request=description)
        search_json = await self._send_json(prompt)
        return search_json.get("search_terms", [description])
