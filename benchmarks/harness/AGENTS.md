---
type: Component
title: Benchmark Harness
description: Scenario execution, judging, scoring, archiving, aggregation, and report rendering internals.
resource: benchmarks/harness/
tags: [benchmarks, harness, scoring]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/harness/`.

# Boundary

`benchmarks/harness/` owns scenario execution, capture, scoring, judging,
archiving, aggregation, and report rendering. It does not parse CLI args or
decide exit codes (`benchmarks/cli/`) and does not define scenarios.

# Contents

- `runner.py` — `run_scenario_once`: seeds dice, assembles the panel, calls
  `_run_execution.execute_scenario`, builds the `ScenarioReport`.
- `_run_execution.py` — builds the engine (safety off, temperature overrides),
  drives scripted turns, snapshots state, scores.
- `transcript.py` (`NarratorCapture`), `snapshots.py` (deep-copy snapshots and
  lookup helpers), `_reliability_capture.py`, `_temperature_override.py`.
- Scoring: `scoring.py` (deterministic + proportional evidence credit),
  `judge.py`, `_judge_vote.py`, `_judge_text.py` (quote verification),
  `panel.py` (`DEFAULT_ROSTER`), `prose_quality.py` (reusable judge specs).
- Persistence: `archive.py`, `_archive_naming.py`, `_serialise.py`,
  `aggregate.py`, `aggregate_archive.py`, `baselines.py`,
  `_baselines_codec.py`, `golden.py`, `_golden_read.py`.
- Markdown report: `report.py` plus `_report_*.py`.
- `types/` — shared dataclasses; `bayes/` — Bayesian comparison layer.

# Local Rules

- Keep typed report structures in [benchmark harness types](/benchmarks/harness/types/AGENTS.md).
- Preserve deterministic execution boundaries for regression comparison.
- Do not run paid judge panels without approval.
- Test offline with stub engines/clients (`tests/test_benchmarks_scoring.py`,
  `tests/test_benchmarks_judge.py`, `tests/test_benchmarks_transcript.py`).

# Patterns

- Benchmark-only engine knobs enter through `create_engine(...)` arguments in
  `_run_execution._prepare_engine`, never via production code paths.
- Seed per-iteration randomness from a stable hash: `runner._dice_seed` uses
  `zlib.crc32`, not `hash()` (ADR-0015).
- A failed judge becomes an `ERROR` vote under its own `model_id`
  (`_judge_vote._error_vote`); `scoring._aggregate_verdict` drops it.
- New prose-quality checks: add a factory returning `EvidencePromptSpec` with
  YES = good to `prose_quality.py` (used by `escalation_guard_assault`).
- Add new serialised fields with defaults read via `.get(key, default)`, as
  `_baselines_codec._rate_from_dict` does for `k_yes` / `n_votes`.

# Anti-patterns

- Calling `load_temperature_overrides()` outside this harness; production must
  ignore benchmark env vars
  (`docs/decisions/0003-engine-temperature-pinning-in-benchmark-mode.md`).
- Editing `DEFAULT_ROSTER` or `_JUDGE_MAX_TOKENS` (keep >= 4096), or falling
  back to another provider for a failed judge
  (`docs/decisions/0019-refresh-judge-panel-to-current-models.md`).
- Even judge caps: a 3-3 split rounds 1-point elements to 0 (ADR-0013).
- Built-in `hash()` for seeds: it is per-process salted
  (`tests/test_benchmarks_runner_seed.py`).
- Writing golden snapshots from regular runs or CI; `golden-update` is
  explicit and per-scenario
  (`docs/decisions/0016-golden-narration-snapshot-workflow.md`).

# Related

- [Benchmarks](/benchmarks/AGENTS.md)
- [Benchmark scenarios](/benchmarks/scenarios/AGENTS.md)
- [Benchmark harness types](/benchmarks/harness/types/AGENTS.md)
- [Bayesian layer](/benchmarks/harness/bayes/AGENTS.md)
- [Benchmark CLI](/benchmarks/cli/AGENTS.md)
