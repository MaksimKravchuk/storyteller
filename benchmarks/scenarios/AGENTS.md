---
type: Component
title: Benchmark Scenarios
description: Deterministic scenario definitions, scripts, expected elements, and seeded states for narrative-quality checks.
resource: benchmarks/scenarios/
tags: [benchmarks, scenarios, evaluation]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/scenarios/`.

# Boundary

`benchmarks/scenarios/` owns deterministic benchmark scenario packages: seed
state, scripted player actions, and scoring rubrics. Running, judging, and
archiving belong in `benchmarks/harness/`.

# Contents

- `_registry.py` — `ALL_SCENARIOS` (auto-discovered, sorted by id) and
  `get_scenario(id)`.
- `_shared.py` — `NPCSpeaksOn` predicate, `npc_name_matches`,
  `EVIDENCE_QUOTE_CHAR_BUDGET`.
- `<scenario_id>/` packages, each with `_scenario.py` (`SCENARIO`),
  `state.py` (`build_state`), `script.py` (`SCRIPT`), `elements.py`
  (`ELEMENTS`). Extra private helpers are allowed (`_moods.py`,
  `npc_autonomy_murder_plot/_detectors.py`).
- `memory_follow_up_marcus_graph_only/` reuses Marcus's script and elements
  and only swaps the seed state.

# Local Rules

- Each scenario should keep state, script, expected elements, and scenario
  registration explicit.
- Release-relevant scenario additions need an approved run and rubric output.
- Keep shared scenario helpers generic and deterministic.
- The package directory name must equal `SCENARIO.id`; baselines and archives
  are keyed by that id.
- Unit-test deterministic predicates offline
  (`tests/test_benchmarks_scenario_elements.py`,
  `tests/test_benchmarks_memory_return_visit.py`).

# Patterns

- New scenario: copy `memory_follow_up_marcus/`. Discovery needs only a
  package exposing `_scenario.SCENARIO`; do not edit `_registry.py`.
- Seed ids with `benchmarks._uuid_helpers.make_uuid("npc-...")`, as in
  `memory_follow_up_marcus/state.py`.
- `build_state()` must build a fresh `GameState` on every call
  (`tests/test_benchmarks_registry.py::test_build_state_is_idempotent`).
- Prefer deterministic `Element`s over judge calls where a fact can be checked
  in code: `NPCSpeaksOn`, snapshot helpers from `benchmarks/harness/snapshots.py`.
- Reuse judge specs from `benchmarks/harness/prose_quality.py`
  (`escalation_guard_assault/elements.py`).

# Anti-patterns

- Putting a fixed-set membership test on the judge panel: it adds cost and
  judge noise. `scene_builder_re_entry_consistency` made it deterministic with
  `_LANDMARK_ALIASES` (ADR-0013;
  `tests/test_benchmarks_scene_builder_predicate.py`).
- Adding a per-scenario import to `_registry.py`; it defeats discovery and the
  module-import budget.
- Re-implementing "NPC X spoke on turn N" per scenario instead of
  `_shared.NPCSpeaksOn`.
- Changing a pinned scenario's script or rubric without re-pinning: the
  baseline in `benchmarks/baselines/` stops being comparable (ADR-0002).

# Related

- [Benchmarks](/benchmarks/AGENTS.md)
- [Benchmark harness](/benchmarks/harness/AGENTS.md)
- [Benchmark harness types](/benchmarks/harness/types/AGENTS.md)
- [Benchmark tests](/tests/benchmarks/AGENTS.md)
