"""Data Miner — researches real-world information to create grounded settings."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from cast import _reliability_metrics as reliability_metrics, base_performer_class as _bpc
from cast.schemas.setting_response import SearchTermsResponse, SettingResponse
from knowledge import graph as knowledge_graph, node as knowledge_node
from llm.base_client import BaseLLMClient
from loguru import logger
from models.setting import Setting
from prompts import data_miner_prompts
from research import base_search_client, wikipedia_search_client

# The synthesised ``Setting`` JSON (key persons, events, locations, traditions,
# technologies, plus prose summary) routinely exceeds the global 2048 default
# and gets truncated mid-stream, breaking JSON parsing. 8000 leaves headroom
# for non-trivial real-world settings without paying for unbounded output.
_RESEARCH_MAX_TOKENS = 8000
# Number of search hits folded into a single FACT node by ``ensure_fact``.
_FACT_RESULT_LIMIT = 3


def _result_to_dict(hit: base_search_client.SearchResult) -> dict[str, str]:
    """Flatten a search hit into the JSON shape fed to the synthesis prompt."""
    return {"title": hit.title, "url": hit.url, "snippet": hit.snippet}


class DataMiner(_bpc.BasePerformer):
    """Researches historical / geographical data via Wikipedia and synthesises
    it into a structured ``Setting`` for the game.
    """

    def __init__(
        self,
        *,
        llm_client: BaseLLMClient,
        search_client: base_search_client.BaseSearchClient | None = None,
        language: str = "English",
    ):
        prompts = data_miner_prompts.get_data_miner_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=prompts.system,
        )
        self._search_terms_template = prompts.search_terms
        self._research_template = prompts.research
        self._search = search_client or wikipedia_search_client.WikipediaSearchClient()
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

        # Step 2: Fetch research results for every term concurrently
        raw_articles = await self._gather_research(search_terms)

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
        graph: knowledge_graph.KnowledgeGraph,
    ) -> knowledge_node.KnowledgeNode | None:
        """Look up or create a world-scoped FACT node for ``name``.

        On a cache miss, searches the configured backend for ``name`` and
        writes a new ``KnowledgeNode`` to ``graph`` with ``scope=WORLD`` and
        ``source=FACT``. The node text is the top result's snippet on the
        Wikipedia backend (a single encyclopedic extract) or the top three
        snippets concatenated on a multi-result backend (Tavily, SearXNG).
        Uses a per-entity ``asyncio.Lock`` so concurrent callers for the same
        name deduplicate to exactly one fetch. Returns ``None`` on any failure
        without raising.
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
                logger.exception("ensure_fact: failed to fetch research summary for {!r}", name)
                reliability_metrics.record_fallback("data_miner", "ensure_fact")
                return None

    async def _fetch_and_store_fact(
        self,
        name: str,
        kind: str | None,
        graph: knowledge_graph.KnowledgeGraph,
    ) -> knowledge_node.KnowledgeNode | None:
        hits = await self._search.search(name, max_results=_FACT_RESULT_LIMIT)
        snippets = [hit.snippet for hit in hits[:_FACT_RESULT_LIMIT] if hit.snippet]
        text = "\n\n".join(snippets)
        if not text:
            logger.warning("ensure_fact: empty search result for {!r}", name)
            return None
        node = knowledge_node.KnowledgeNode(
            text=text,
            scope=knowledge_node.KnowledgeScope.WORLD,
            source=knowledge_node.KnowledgeSource.FACT,
            tags=list(filter(None, ["historical_fact", kind])),
        )
        self._fact_cache[name] = graph.add_node(node)
        return node

    async def _gather_research(self, search_terms: list[str]) -> dict[str, list[dict]]:
        """Search every term concurrently and flatten the hits per term."""
        searches = [self._search.search(term) for term in search_terms]
        per_term = await asyncio.gather(*searches)
        raw: dict[str, list[dict]] = {}
        for term, hits in zip(search_terms, per_term):
            raw[term] = [_result_to_dict(hit) for hit in hits]
        return raw

    async def _extract_search_terms(self, description: str) -> list[str]:
        """Ask the LLM to generate Wikipedia search terms."""
        prompt = self._search_terms_template.format(setting_request=description)
        search_json = await self._send_json(prompt, response_model=SearchTermsResponse)
        return search_json.search_terms or [description]
