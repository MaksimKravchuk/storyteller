---
type: Component
title: Benchmark CLI
description: Command-line entry points for running, comparing, calibrating, pinning, and reporting benchmark outputs.
resource: benchmarks/cli/
tags: [benchmarks, cli, evaluation]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/cli/`.

# Boundary

`benchmarks/cli/` owns argument parsing, command dispatch, verdict formatting
and exit codes for benchmark workflows. Scenario execution, judging, scoring
and archive IO belong in `benchmarks/harness/`.

# Contents

- `_main.py` — `main()`: configures loguru, parses args, dispatches via
  `_async_commands.py` (`run`, `calibrate`, `golden-update`) or
  `_sync_commands.py` (`compare`, `pin`, `baselines`, `bayes-report`,
  `pr-comment`, `narration-diff`, `reliability-report`).
- `_args.py`, `_args_subcommands.py`, `_arg_types.py` — argparse setup.
- `run`: `_run.py`, `_jobs.py`, `_aggregate_flow.py`, `_summary.py`,
  `_run_compare.py`, `_auto_compare.py` (ADR-0002 gate + ratchet).
- `compare`: `_compare.py`, `_compare_classify.py`, `_compare_format.py`.
- Baselines: `_pin.py`, `_baselines.py`; calibration: `_calibrate*.py`.
- Bayesian / PR comment: `_bayes_report.py`, `_bayes_format.py`,
  `_scenario_verdict.py`, `_results_aggregates.py`, `_pr_comment*.py`.
- Archive readers: `_iteration_archives.py`, `_narration_diff*.py`,
  `_reliability_report.py`, `_reliability_table.py`, `_golden_update.py`.

# Local Rules

- Keep CLI parsing separate from scoring and execution internals.
- Add tests for command dispatch, output formatting, and error paths
  (`tests/test_benchmarks_cli.py`, `tests/test_benchmarks_pr_comment.py`, ...).
- Offline commands (`compare`, `bayes-report`, `pr-comment`, `narration-diff`,
  `reliability-report`, `pin`) must stay pure file IO with no LLM calls.

# Patterns

- New subcommand: register its parser in `_args_subcommands.py`, write
  `<name>_command(args) -> int` in its own module, add it to
  `SYNC_COMMANDS` or `ASYNC_COMMANDS`.
- Isolate per-iteration crashes and keep going, as `_run._run_one` and
  `_calibrate.py` do; count failures and decide the exit code at the end.
- Share logic between commands in one module instead of copying it:
  `_scenario_verdict.py` (bayes-report + pr-comment),
  `_iteration_archives.py` (narration-diff + reliability-report).
- Rebuild aggregates with `_baselines_codec.aggregate_from_dict`, as
  `_pin.py` does, so `k_yes`/`n_votes` tallies survive a re-pin.

# Anti-patterns

- Driving the exit code from the Bayesian `P(regression)`; the k-sigma
  classifier in `_auto_compare.py` is the only gate (ADR-0013).
- Exiting 1 on `no_baseline`, or exiting non-zero under `--no-compare`
  (ADR-0002; `tests/test_benchmarks_run_auto_compare.py`,
  `tests/test_benchmarks_run_isolation.py`).
- Letting a crashed scenario suppress other scenarios' `[auto-compare]` lines;
  CI greps them (`tests/test_benchmarks_run_isolation.py`).
- Loosening the ratchet below strict `delta > 2 * noise_floor_stdev`
  (`should_ratchet`, ADR-0002).
- Removing the loguru `diagnose` setting in `_main.py`: tracebacks leaked
  Config secrets into CI logs (#380; `tests/test_benchmarks_cli_logging.py`).
- Counting duplicate aggregates per scenario in `bayes-report`; it must
  dedupe by `scenario_id` (ADR-0013; `tests/test_benchmarks_bayes_cli.py`).

# Related

- [Benchmarks](/benchmarks/AGENTS.md)
- [Benchmark harness](/benchmarks/harness/AGENTS.md)
- [Bayesian layer](/benchmarks/harness/bayes/AGENTS.md)
