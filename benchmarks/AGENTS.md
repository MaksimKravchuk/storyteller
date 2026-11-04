---
type: Component
title: Benchmarks
description: Deterministic narration-quality benchmark harness, scenarios, model panels, and comparison tooling.
resource: benchmarks/
tags: [benchmarks, evaluation, narrative-quality]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/`.

# Boundary

`benchmarks/` owns deterministic narrative-quality scenarios, harness execution,
judging, scoring, comparison, and result archiving. It drives the engine from
the outside (`engine.factory`); it must not hold engine, prompt, or agent logic.

# Contents

- `__main__.py` — `python -m benchmarks` entry; delegates to `cli/_main.py`.
- `_uuid_helpers.py` — `make_uuid(label)`: deterministic UUID4 from a readable
  label, mirroring `tests/_uuid_helpers.py`.
- `cli/` — subcommands (`run`, `compare`, `pin`, `calibrate`, `bayes-report`,
  `pr-comment`, `narration-diff`, ...).
- `harness/` — runner, judge panel, scoring, archive, reports; `harness/bayes/`
  holds the Bayesian comparison layer.
- `scenarios/` — one package per scenario, auto-discovered by `_registry.py`.
- `model_sets/` — offline cross-model-set comparison tooling.
- `baselines/` — git-tracked pinned per-scenario baselines
  (`<scenario_id>.json`) plus `.calibration.json` (noise floor). Written only by
  `benchmarks pin` / `calibrate` (ADR-0002).
- `results/` — timestamped per-iteration `*_iter*.json`/`.md` and
  `*_aggregate.json`/`.md` archives written by `harness/archive.py`;
  `set-<name>__` prefixes come from `model_sets/run_sets.sh`. Historical
  archives are tracked in git (`model_sets/` reads them); CI workflows delete
  them before a run so only fresh results are compared.

# Local Rules

- Benchmark runs can hit paid LLM APIs; run them only after approval.
- Scenario changes should include a release-relevant rubric run when approved.
- Keep CLI behavior coordinated with [benchmark CLI](/benchmarks/cli/AGENTS.md)
  and execution internals in [benchmark harness](/benchmarks/harness/AGENTS.md).
- Unit tests for this package live in `tests/test_benchmarks_*.py` and are
  offline; the paid end-to-end path is `tests/benchmarks/` (`-m benchmark`).

# Patterns

- Seed fixtures with `make_uuid("npc-marcus-baker")` (see
  `scenarios/memory_follow_up_marcus/state.py`) so ids are stable across runs.
- Change a baseline only via `benchmarks pin <id> --from <aggregate.json>`
  (`cli/_pin.py`), which stamps `noise_floor_stdev` from `.calibration.json`.

# Anti-patterns

- Hand-editing or auto-pinning `baselines/*.json`: PR-diff review of pins is
  the human checkpoint; CI must never pin (ADR-0002, ADR-0009).
- Moving baselines into `results/`: the gate reads only `baselines/`
  (`docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`).
- Changing engine pins or the judge roster without re-calibrating and
  re-pinning: baselines record `engine_models` and the panel
  (`docs/decisions/0018-default-agent-roles-to-gpt-6-luna.md`,
  `docs/decisions/0019-refresh-judge-panel-to-current-models.md`).

# Related

- [Benchmark CLI](/benchmarks/cli/AGENTS.md)
- [Benchmark harness](/benchmarks/harness/AGENTS.md)
- [Benchmark scenarios](/benchmarks/scenarios/AGENTS.md)
- [Benchmark model sets](/benchmarks/model_sets/AGENTS.md)
- [Benchmark tests](/tests/benchmarks/AGENTS.md)
- [Cast](/cast/AGENTS.md)
- [Engine](/engine/AGENTS.md)
- [Prompts](/prompts/AGENTS.md)
