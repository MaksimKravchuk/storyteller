---
type: Component
title: Benchmark Bayesian Layer
description: Pure-stdlib Bayesian posteriors that grade benchmark aggregates against pinned baselines.
resource: benchmarks/harness/bayes/
tags: [benchmarks, bayesian, statistics, reporting]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/harness/bayes/`.

# Boundary

`benchmarks/harness/bayes/` owns the read-only Bayesian comparison of a current
aggregate against its pinned baseline (ADR-0013). It takes aggregate dicts and
returns result dataclasses. It does no file IO, CLI formatting, or LLM calls,
and it never decides an exit code.

# Contents

- `_report.py` — public functions: `verdict_for_scenario(baseline, current,
  noise_floor_stdev=...)`, `portfolio_verdict(...)`, `DEFAULT_ROPE = 0.5`.
- `_types.py` — frozen result dataclasses: `Sample`, `BetaParams`,
  `VoteCounts`, `DeltaPosterior`, `ElementInferiority`, `ScenarioVerdict`,
  `PortfolioVerdict`.
- `_normal.py` — conjugate Normal total delta scaled by the baseline's
  `noise_floor_stdev`; `pool_deltas` for the portfolio-bias line.
- `_beta.py` — `element_inferiority`: per-element Beta-Binomial with the
  judge votes -> pass-counts -> flat-prior fallback chain.
- `_beta_quadrature.py` — `prob_below`: trapezoid quadrature on a fixed
  1000-step grid.
- `__init__.py` — docstring only; import from `_report` and `_types`.

# Local Rules

- Callers live in `benchmarks/cli/` (`_scenario_verdict.py`, `_compare.py`,
  `_bayes_format.py`); keep text formatting there, not here.
- Tests are sync and offline: `tests/test_benchmarks_bayes.py` for the math,
  `tests/test_benchmarks_bayes_cli.py` for the CLI seam.
- Any change to the ROPE, grid, or fallback chain needs an ADR-0013 update.

# Patterns

- Read aggregate dicts defensively, as `_report._counts` does with
  `rate.get("k_yes", 0)`, so pre-tally baselines still score.
- Match elements by `element_id` and skip ones missing from the baseline
  (`_report._element_verdicts`).
- Handle degenerate inputs (zero noise floor, zero votes) explicitly; see
  `test_zero_noise_floor_is_degenerate` and `test_no_data`.

# Anti-patterns

- Importing numpy/scipy or using an RNG / Monte Carlo sampling: the advisory
  PR comment must be reproducible and dependency-free
  (`docs/decisions/0013-bayesian-benchmark-comparison-layer.md`, Alternative 4).
- Routing the `run` exit code or `[auto-compare]` verdict through
  `P(regression)`; the frequentist gate in `benchmarks/cli/_auto_compare.py`
  stays the only gate (ADR-0013, Alternative 2).
- Using the current run's `stdev_awarded` as the noise scale when a pinned
  `noise_floor_stdev` exists (ADR-0002, ADR-0013).

# Related

- [Benchmark harness](/benchmarks/harness/AGENTS.md)
- [Benchmark harness types](/benchmarks/harness/types/AGENTS.md)
- [Benchmark CLI](/benchmarks/cli/AGENTS.md)
