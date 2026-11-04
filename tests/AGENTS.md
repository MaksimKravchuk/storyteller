---
type: Component
title: Tests
description: Deterministic unit, integration, DB, E2E, and benchmark test guidance.
resource: tests/
tags: [tests, quality, allure]
---

# Directory Instructions

Root `AGENTS.md`, `CLAUDE.md`, and `tests/README.md` remain authoritative. This
file adds local context for `tests/`.

# Boundary

`tests/` owns automated verification. Non-e2e tests must use Allure epic,
feature, story, and title labels. Production code must not import from here.

# Contents

- `test_*.py` — flat unit-test layout; Allure groups them by epic/feature.
- `conftest.py` — shared fixtures (`loguru_sink`, `simple_setting`,
  `populated_graph`, `game_state`, `sample_npc`, `sample_location`) and the
  `pytest_collection_modifyitems` Allure-label enforcement hook.
- `_db_stubs.py` — stubs `db.engine` / `db.repository` in `sys.modules` so
  unit tests never open a real connection.
- `director_helpers.py`, `actor_helpers.py`, `base_performer_helpers.py`,
  `_uuid_helpers.py` and other `_*_helpers.py` — shared builders and mocks.
- `TEST_TAXONOMY.md` — the epic/feature table; source of truth for labels.
- `fixtures/` — recorded data (`tests/fixtures/moderation_scores.json`)
  and its re-record script (`tests/fixtures/record_moderation_scores.py`).
- `e2e/`, `db/`, `benchmarks/`, `prompts/` — see their own AGENTS.md files.

# Local Rules

- For bug fixes, write and observe the failing regression test before the fix.
- Prefer consumer-side integration seams for wiring regressions.
- Do not add lint, type, or test suppressions without explicit approval.
- Paid E2E and benchmark checks require approval.
- Markers `db`, `benchmark`, `live` are deselected by default via
  `addopts` in `pyproject.toml`; opt in with `-m <marker>`.
- Async tests do not count toward mutmut's kill score: `[tool.mutmut]`
  deselects `asyncio`-marked tests. Code in the mutation scope needs sync
  tests that assert its behavior.

# Patterns

- Labels: class-level `@allure.epic` / `@allure.feature`, method-level
  `@allure.story` / `@allure.title`, as in `tests/test_dice.py`; or a
  module `pytestmark = [allure.epic(...), ...]` list as in
  `tests/prompts/test_actor_derived_mood_seam.py`.
- Director tests build state with `make_director` / `make_game_state` /
  `setup_npc` from `tests/director_helpers.py`.
- Stable IDs come from `make_uuid(label)` in `tests/_uuid_helpers.py`.
- Seam tests are named `*_seam.py` (e.g. `test_data_miner_search_seam.py`,
  `test_director_npc_occupation_seam.py`) and assert on what the consumer
  receives, not on the supplier's return value.
- Live external-API smoke tests carry `pytest.mark.live`, as in
  `tests/test_tavily_live.py`.

# Anti-patterns

- Missing Allure labels: collection fails with `pytest.UsageError`
  (`tests/conftest.py`), so the whole run breaks, not just one test.
- Importing real `db.engine` in a unit test: `_db_stubs.py` is loaded first
  by `tests/conftest.py`; real DB work belongs in `tests/db/`.
- Supplier-only tests for a new field: the `known_names_for_player` regression
  passed supplier tests but never reached the Narrator prompt (ADR-0002,
  `docs/decisions/0002-prompt-consumer-seam-contract-tests.md`).
- Keeping prod helpers alive only for tests: removed in `cb9e9fb` (#389).

# Related

- [E2E tests](/tests/e2e/AGENTS.md)
- [DB tests](/tests/db/AGENTS.md)
- [Benchmark tests](/tests/benchmarks/AGENTS.md)
- [Prompt seam tests](/tests/prompts/AGENTS.md)
- [Benchmarks](/benchmarks/AGENTS.md)
