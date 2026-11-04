---
type: Component
title: Benchmark Model Sets
description: Helpers for gathering, scoring, formatting, and comparing benchmark model-set runs.
resource: benchmarks/model_sets/
tags: [benchmarks, model-sets, evaluation]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/model_sets/`.

# Boundary

`benchmarks/model_sets/` supports multi-model benchmark comparison workflows:
run the suite under alternate engine model sets, then compare archives
offline. It reuses `benchmarks run`; it must not run scenarios or judges itself.

# Contents

- `run_sets.sh` — paid driver: runs `benchmarks run` per (set, scenario) with
  env-var model pins for `max` / `optimal` / `economy`, then renames new
  archives to `set-<name>__<stem>`. Idempotent; logs to a local logs dir.
- `smoke.py` — paid connectivity ping for each set's models via
  `AI_MODELS`; needs `OPENROUTER_API_KEY`.
- `compare.py` — offline entry; renders a comparison.md report from
  `benchmarks/results/` (the report and logs dir are git-ignored).
- `_patterns.py` (archive filename regexes), `_gather.py` (aggregate first,
  per-iteration fallback), `_score.py` (`SetScore`), `_format.py`,
  `_render.py` (`Comparison`, `render`).
- No `__init__.py`: imported as a namespace package.

# Local Rules

- Keep model-set comparison separate from core scenario execution.
- Do not run paid model-set checks (`run_sets.sh`, `smoke.py`) without approval.
- Keep the scenario list in `run_sets.sh` and `compare.py` in sync.
- Offline modules are unit-tested in `tests/test_benchmarks_model_sets_*.py`.

# Patterns

- Identify archives by filename only, via the anchored regexes in
  `_patterns.py`; untagged aggregates are the `baseline` column.
- Fall back to per-iteration JSONs when a set has no aggregate
  (`_gather._set_score`) so partial runs still show their iteration count.

# Anti-patterns

- Loose filename matching: a scenario id that is a prefix of another must not
  match (`tests/test_benchmarks_model_sets_patterns.py`,
  `test_rejects_scenario_id_substring_collision`).
- Treating set runs as pinned baselines or `pin`-ning them: set runs swap the
  engine models the baselines record (ADR-0002, ADR-0018).
- Hard-coding model ids that drift from `defaults/models.py`: `run_sets.sh`
  kept the retired `claude-sonnet-4-20250514` long after #325 removed it from
  the judge panel. When a model retires, update `run_sets.sh` with it
  (`docs/decisions/0019-refresh-judge-panel-to-current-models.md`).

# Related

- [Benchmarks](/benchmarks/AGENTS.md)
- [LLM](/llm/AGENTS.md)
