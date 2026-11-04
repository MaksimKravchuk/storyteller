---
type: Component
title: Benchmark Tests
description: Benchmark harness tests, from no-LLM detector and snapshot checks to the opt-in paid scenario runs.
resource: tests/benchmarks/
tags: [tests, benchmarks, golden, temperature]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `tests/benchmarks/`.

# Boundary

`tests/benchmarks/` holds the pytest entry for paid scenario runs plus fast,
synthetic-data tests of harness pieces. Most harness unit tests live flat in
`tests/test_benchmarks_*.py`; put new no-LLM harness tests there unless they
belong to a group already here.

# Contents

- `test_scenarios.py` — the only paid test: parametrizes `ALL_SCENARIOS`
  through `run_scenario_once`, marked `@pytest.mark.benchmark`.
- `test_golden_narration.py` — no-LLM golden narration snapshot checks
  (ADR-0016).
- `test_temperature_override.py`, `test_temperature_override_seam.py`,
  `_temperature_test_env.py` — env parsing and the consumer seam into the
  engine factory (ADR-0003).
- `test_calibrate_drift.py`, `test_calibrate_drift_table.py` — drift math.
- `test_npc_autonomy_murder_plot_detectors.py` — rubric detector logic.

# Local Rules

- Never run `-m benchmark` without Max's approval; it hits paid LLMs.
- The `benchmark` marker is deselected by default, so CI's unit job runs the
  rest of this directory; keep those tests free of network and LLM calls.
- This directory is exempt from the Allure hook, but new files should still
  use a module `pytestmark` with `allure.epic("Benchmarks")` and a feature.

# Patterns

- Consumer-seam style for harness wiring: `test_temperature_override_seam.py`
  asserts the env value reaches the factory's `temperature_override` kwarg
  through `_prepare_engine`, not just that the parser returns it.
- Shared env setup lives in a `_`-prefixed helper module
  (`_temperature_test_env.py`) rather than a conftest.
- Detector regressions get a synthetic `CapturedTurn` test, as
  `test_npc_autonomy_murder_plot_detectors.py` does for the concealed-weapon
  false positive on `clash_occurred`.

# Anti-patterns

- Re-pinning golden snapshots to make `test_golden_narration.py` pass:
  ADR-0016 requires an intentional, evidenced re-pin, and golden diffs are
  not a quality ratchet.
- Unpinned temperature or dice in scenario runs: ADR-0003 and ADR-0015
  pin both so benchmark runs are comparable.
- Adding the `benchmark` marker to a cheap test: it silently drops out of CI.

# Related

- [Tests](/tests/AGENTS.md)
- [Benchmarks](/benchmarks/AGENTS.md)
- [Harness](/benchmarks/harness/AGENTS.md)
- [Scenarios](/benchmarks/scenarios/AGENTS.md)
- [Bayes](/benchmarks/harness/bayes/AGENTS.md)
