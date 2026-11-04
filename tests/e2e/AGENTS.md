---
type: Component
title: E2E Tests
description: Live-provider smoke tests that drive each performer and a full session against real LLMs.
resource: tests/e2e/
tags: [tests, e2e, live-llm, allure]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `tests/e2e/`.

# Boundary

`tests/e2e/` owns real-LLM checks: one `test_<agent>_real.py` per performer
plus a full-session narrative-quality run. Every test here costs money. Mocked
or deterministic tests belong in `tests/`, not here.
Every test file carries `pytestmark = pytest.mark.live`, so the default run
deselects it; run with `-m live`. CI runs this suite only in
`.github/workflows/live-api.yml` (manual dispatch or the `live-api` PR label),
never in `.github/workflows/ci.yml`.

# Contents

- `test_<agent>_real.py` — per-performer smoke tests (actor, data_miner,
  dramaturge, narrator, npc_generator, scene_builder, world_chronicler) and
  `test_director_agentic_delegation.py` for the Director.
- `_real_llm.py` — `real_llm_for(agent)`: config -> model -> API key ->
  client, or `pytest.skip` naming the missing `*_API_KEY`.
- `_agent_matrix.py` — `AgentKey`, `ALL_AGENTS`, glob rules mapping changed
  paths to agents, and the agent -> test-file map.
- `_select_agents.py` — CI selector run as
  `python -m tests.e2e._select_agents --base <ref>`; honours
  `PYTEST_AGENT_TESTS` (`all`, `none`, `a,b`).
- `test_narrative_quality.py` with `narrative_session_driver.py`,
  `narrative_test_agent.py` (LLM judge), `narrative_report.py`,
  `session_transcript.py` — scripted live session scored on six rubrics.
- `conftest.py` — only installs the log secret scrubber.

# Local Rules

- Do not run anything here without Max's approval; it hits paid providers.
- Exempt from the unit-test Allure hook, but still label tests: epic
  `AI Agent Orchestration`, a `<Agent> real-model ...` feature, plus story
  and title.
- Get clients only through `real_llm_for`, so a missing key skips rather
  than errors.
- Adding a performer: add its key to `AgentKey`/`ALL_AGENTS`, its model
  attr in `AGENT_TO_MODEL_ATTR`, its file in the matrix, and glob rules.

# Patterns

- Assert on distinctive input values surviving into output (a rare NPC
  name, a unique POI), as `tests/e2e/test_narrator_real.py` does with
  `_NPC_NAME` / `_POI_NAME`; never on exact prose.
- Build fixtures with `tests/director_helpers.py` and stable IDs with
  `make_uuid` from `tests/_uuid_helpers.py`.
- Attach long outputs with `allure.attach`, as in
  `narrative_session_driver.py`.

# Anti-patterns

- Constructing clients directly: bypasses the skip-with-hint path and the
  `AGENT_TO_MODEL_ATTR == ALL_AGENTS` drift assert in `_real_llm.py`.
- Letting keys drift between the two maps: a typo'd key silently drops out
  of selection and CI skips the e2e step (see `_agent_matrix.py` docstring).
- Relying on skips for coverage: `.github/workflows/live-api.yml` fails loud if
  `OPENAI_API_KEY` is missing, since all-skipped e2e would pass green with zero real coverage.

# Related

- [Tests](/tests/AGENTS.md)
- [Cast](/cast/AGENTS.md)
- [LLM](/llm/AGENTS.md)
