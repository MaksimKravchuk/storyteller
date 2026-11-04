---
type: Component
title: Benchmark Harness Types
description: Typed benchmark reports, captures, scenario definitions, scores, and aggregate structures.
resource: benchmarks/harness/types/
tags: [benchmarks, types, reports]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/harness/types/`.

# Boundary

`benchmarks/harness/types/` owns typed benchmark report, capture, scenario,
score, and aggregate structures. It holds plain dataclasses with constructor
validation only; no IO, scoring logic, or LLM calls.

# Contents

- `_elements.py` — `Element`, `EvidencePromptSpec`, `DeterministicResult`,
  `DeterministicCheck`, and the `KIND_DETERMINISTIC` / `KIND_EVIDENCE_LLM` kinds.
- `_scenarios.py` — `Scenario`, `ScriptTurn`, `ScenarioState` (seed state for
  `engine.restore_session`).
- `_captures.py` — `CapturedTurn` (narration + `TurnOutputs` per turn).
- `_scores.py` — `JudgeVote`, `ElementScore`, `PanelMember`,
  `SkippedCandidate`, `ScenarioReport`.
- `_aggregates.py` — `ElementPassRate`, `ScenarioAggregate`, `PinnedBaseline`.
- `__init__.py` — docstring only; there are no re-exports.

# Local Rules

- Coordinate type changes with archive serialization and report rendering.
- Add tests for backward-compatible archive reads when shape changes.
- Import from the concrete module (`benchmarks.harness.types._scores`), or the
  module itself under `TYPE_CHECKING` as `_run_execution.py` does.

# Patterns

- Frozen dataclasses with invariants checked in `__post_init__`, e.g.
  `Element` (positive `base_value`, kind/check match) and `Scenario`
  (non-empty script, unique element ids).
- New fields go last with a default (`ScenarioReport.reliability_counts`,
  `ElementPassRate.k_yes` / `n_votes`) so older archives still load.
- Engine and model types stay behind `TYPE_CHECKING` imports
  (`_captures.py`, `_elements.py`) to keep this package import-light.

# Anti-patterns

- Adding a required field to `ElementPassRate` or `ScenarioAggregate`:
  pinned baselines in `benchmarks/baselines/` predate it and must still load
  (ADR-0013; `tests/test_benchmarks_pin.py::test_preserves_judge_tallies`).
- Folding `PinnedBaseline.noise_floor_stdev` into
  `ScenarioAggregate.stdev_awarded`; the noise floor belongs to the baseline,
  not the run (`docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`).
- Changing a field without updating `_baselines_codec.py` and `_serialise.py`
  in `benchmarks/harness/`; the archive and pin round-trip would drop it.

# Related

- [Benchmark harness](/benchmarks/harness/AGENTS.md)
- [Bayesian layer](/benchmarks/harness/bayes/AGENTS.md)
- [Models](/models/AGENTS.md)
