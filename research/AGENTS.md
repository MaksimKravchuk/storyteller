---
type: Component
title: Research
description: External research clients used by setting generation and fact enrichment.
resource: research/
tags: [research, wikipedia, integrations]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `research/`.

# Boundary

`research/` owns external information clients used by performer agents such as
DataMiner. It returns raw search results only: prompt shaping, untrusted-data
guards and knowledge-node creation stay in `cast/` and `prompts/`.

# Contents

- `base_search_client.py` — `SearchResult` (frozen dataclass) and the
  abstract `BaseSearchClient.search(query, *, max_results)`.
- `search_factory.py` — `create_search_client(provider, ...)` and the
  `PROVIDER_*` names.
- `wikipedia_search_client.py` — default backend; wraps `WikipediaClient`
  and exposes it as `.wikipedia`.
- `wikipedia_client.py` — httpx client (per-call `AsyncClient`) for Wikipedia REST/MediaWiki.
- `tavily_search_client.py`, `searxng_search_client.py` — httpx clients for
  hosted Tavily and self-hosted SearXNG.

# Local Rules

- Keep live network behavior behind explicit seams.
- Prefer stubbed or recorded integration evidence for behavior changes.
- Do not run credentialed or paid checks without approval.
- The client is chosen at the engine seam (`engine/factory.py`); agents
  receive a `BaseSearchClient`, never a concrete class (ADR-0007).

# Patterns

- New provider: subclass `BaseSearchClient`, add a `PROVIDER_*` constant and
  branch in `create_search_client`, and add it to
  `db.repo_settings_search.ALLOWED_SEARCH_PROVIDERS` for the admin switch.
- Required config is checked in `__init__` and raises `ValueError`
  (`TavilySearchClient`, `SearXNGSearchClient`).
- Soft misses return `[]`: non-200 status, missing article or zero hits
  (`TavilySearchClient.search`).
- Test with patched HTTP clients, no network: `_patch_httpx` in
  `tests/test_search_clients.py`; also `tests/test_search_factory.py` and
  `tests/test_wikipedia_client.py`.

# Anti-patterns

- Do not raise for "no results"; DataMiner treats `[]` as a soft miss
  (ADR-0007, `BaseSearchClient.search` docstring).
- Do not silently fall back to Wikipedia when a provider's key or URL is
  missing; fail fast with `ValueError` (ADR-0007).
- Do not add a provider SDK dependency; Tavily uses raw `httpx` (ADR-0007).
- Do not pass search snippets into prompts unwrapped; they are untrusted and
  go inside `<research_data>` with the do-not-obey guard in both locale
  prompt files (ADR-0007).

# Related

- [Cast](/cast/AGENTS.md)
- [LLM](/llm/AGENTS.md)
- [Engine](/engine/AGENTS.md)
