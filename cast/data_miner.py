"""Data Miner — researches real-world information to create grounded settings."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from cast import _data_miner_init as _dmi, base_performer_class as _bpc
from cast.schemas.setting_response import SearchTermsResponse, SettingResponse
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource
from llm.base_client import BaseLLMClient
from loguru import logger
from models.setting import Setting
from research.wikipedia_client import WikipediaClient

# The synthesised ``Setting`` JSON (key persons, events, locations, traditions,
# technologies, plus prose summary) routinely exceeds the global 2048 default
# and gets truncated mid-stream, breaking JSON parsing. 8000 leaves headroom
# for non-trivial real-world settings without paying for unbounded output.
_RESEARCH_MAX_TOKENS = 8000


class DataMiner(_bpc.BasePerformer):
    """Researches historical / geographical data via Wikipedia and synthesises
    it into a structured ``Setting`` for the game.
    """

    def __init__(
        self,
        *,
        llm_client: BaseLLMClient,
        wikipedia_client: WikipediaClient | None = None,
        language: str = "English",
    ):
        prompts = _dmi.resolve_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=prompts.system,
        )
        self._search_terms_template = prompts.search_terms
        self._research_template = prompts.research
        self.wikipedia = _dmi.resolve_wikipedia_client(wikipedia_client)
        self._fact_cache: dict[str, UUID] = {}  # entity name → node UUID
        self._fact_locks: dict[str, asyncio.Lock] = {}  # per-entity asyncio lock
        self.set_context(language=language)

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
        research_prompt = self._research_template.format(
            setting_request=input_data,
            raw_research=json.dumps(raw_articles, indent=2, ensure_ascii=False),
        )
        setting_data = await self._send_json(
            research_prompt,
            response_model=SettingResponse,
            max_tokens=_RESEARCH_MAX_TOKENS,
        )

        # Build the Setting model
        return Setting(
            name=setting_data.name or "Unknown",
            time_period=setting_data.time_period,
            region=setting_data.region,
            summary=setting_data.summary,
            key_persons=[person.model_dump() for person in setting_data.key_persons],
            key_events=[event.model_dump() for event in setting_data.key_events],
            locations=[location.model_dump() for location in setting_data.locations],
            traditions=setting_data.traditions,
            technologies=setting_data.technologies,
            social_structure=setting_data.social_structure,
        )

    async def ensure_fact(
        self,
        name: str,
        kind: str | None = None,
        *,
        graph: KnowledgeGraph,
    ) -> KnowledgeNode | None:
        """Look up or create a world-scoped FACT node for ``name``.

        On a cache miss, fetches the Wikipedia summary for ``name`` and writes
        a new ``KnowledgeNode`` to ``graph`` with ``scope=WORLD`` and
        ``source=FACT``.  Uses a per-entity ``asyncio.Lock`` so that concurrent
        callers for the same name deduplicate to exactly one Wikipedia fetch.
        Returns ``None`` on any failure without raising.
        """
        cached = self._fact_cache.get(name)
        if cached is not None:
            return graph.get_node(cached)
        lock = self._fact_locks.setdefault(name, asyncio.Lock())
        async with lock:
            cached = self._fact_cache.get(name)
            if cached is not None:
                return graph.get_node(cached)
            try:
                return await self._fetch_and_store_fact(name, kind, graph)
            except Exception:
                logger.exception("ensure_fact: failed to fetch Wikipedia summary for {!r}", name)
                return None

    async def _fetch_and_store_fact(
        self,
        name: str,
        kind: str | None,
        graph: KnowledgeGraph,
    ) -> KnowledgeNode | None:
        summary = await self.wikipedia.get_summary(name)
        extract = summary.get("extract", "")
        if not extract:
            logger.warning("ensure_fact: empty Wikipedia result for {!r}", name)
            return None
        node = KnowledgeNode(
            text=extract,
            scope=KnowledgeScope.WORLD,
            source=KnowledgeSource.FACT,
            tags=list(filter(None, ["historical_fact", kind])),
        )
        self._fact_cache[name] = graph.add_node(node)
        return node

    async def _extract_search_terms(self, description: str) -> list[str]:
        """Ask the LLM to generate Wikipedia search terms."""
        prompt = self._search_terms_template.format(setting_request=description)
        search_json = await self._send_json(prompt, response_model=SearchTermsResponse)
        return search_json.search_terms or [description]
