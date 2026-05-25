# ADR-0002: Benchmark auto-compare on `run` + 2-sigma ratchet predicate

Date: 2026-05-25
Status: Accepted
Decision owner: Max
Related: [Issue #271 — benchmarks: pinned baselines + auto-compare on run + stdev in aggregates], `docs/decisions/0001-feature-factory-default-workflow.md`

## Context

Before this change, the benchmarks CLI shipped two ergonomically separate halves:

1. `python -m benchmarks run` produced per-iteration reports and per-scenario aggregates (mean / min / max only).
2. `python -m benchmarks compare <baseline.json> <current.json>` required the operator to hand-pick two aggregate paths and **always exited 0**, so any regression detection was an eyeball job over two markdown files.

There was no canonical baseline per scenario, no concept of "current main is the reference", and aggregates carried no `stdev` — so there was no statistically defensible way to separate a real regression from engine non-determinism (engine temperature is not pinned in Phase 1). The result is that `benchmarks run` could not be used as a release gate: a real quality regression and a noise bounce looked identical in the output.

The narrative-affecting code paths (`cast/`, `prompts/`, narrator-side wiring) are the very surface this harness exists to protect. Without an automatic verdict, every PR that touches those paths re-litigates "is 7.2 vs 8.1 a regression?" by inspection.

## Decision

Adopt three coupled changes that turn `benchmarks run` into a regression gate while preserving the existing manual-`compare` workflow as a backstop:

1. **Stdev in aggregates.** `ScenarioAggregate` carries `stdev_awarded: float` (population stdev over `iteration_totals`); the JSON archive and markdown sibling both surface it. The manual `compare` header gains a `stdev=` field.
2. **Pinned, git-tracked baselines.** `benchmarks/baselines/<scenario_id>.json` is the canonical per-scenario reference, populated by `benchmarks pin <scenario_id> --from <aggregate.json>`. Each baseline carries metadata: `baselined_at`, `engine_git_sha`, `engine_models`, `iterations`, and `noise_floor_stdev`. The directory is git-tracked so the baseline travels with the repo.
3. **Auto-compare on `run`.** After `finalise_aggregates`, `run_command` calls `_auto_compare.evaluate(aggregates)` and exits `1` when any scenario regresses against its pinned baseline. The verdict rule is:
   - `iterations >= 3` (both sides): k-sigma overlap (`classify_stdev_overlap`, k=1). Regression when current's upper one-sigma band sits strictly below baseline's lower one-sigma band; improvement is the symmetric upward case; overlap is noise.
   - `iterations < 3`: fall back to range-overlap (`classify_range`).
   - No baseline pinned: classification is `no_baseline`, never `regression`, exit code unchanged.
4. **Opt-in calibration + ratchet.** `benchmarks calibrate [--iterations N --scenarios ...]` runs N iterations per scenario (default 5; flags scenarios with `stdev > 0.15 * total_base` and recommends N=10) and writes `benchmarks/baselines/.calibration.json`. The calibrated stdev becomes the baseline's `noise_floor_stdev` at pin time. `benchmarks run --update-baselines-on-improvement` ratchets the baseline forward **only when** `current.mean - baseline.mean > 2 * baseline.noise_floor_stdev` (strict `>`, not `≥`).
5. **Escape hatches.** `benchmarks run --no-compare` skips auto-compare entirely (always exits 0). Ratchet is silent without `--update-baselines-on-improvement`. `benchmarks calibrate` is never run on CI — it hits paid LLMs.

## Rationale

- **Variance is real and must be modelled.** Phase 1 leaves engine temperature un-pinned. A single mean-difference threshold cannot separate "the model is actually worse" from "today's roll landed lower." Carrying stdev on every aggregate and gating on a k-sigma overlap is the cheapest statistically honest verdict for N=3 iterations per scenario.
- **2-sigma is the safe ratchet multiplier.** Using `delta > 1 * noise_floor_stdev` would let a single lucky roll permanently raise the bar against the engine's known variance; `delta > 2 * noise_floor_stdev` requires the new mean to clear the upper 95% band of the calibrated noise floor. Strict `>` (not `≥`) avoids ratcheting on the exact boundary where calibration is imprecise.
- **Calibrated noise_floor_stdev ≠ current run's stdev.** The aggregate's `stdev_awarded` is descriptive — the variance observed *in this run*. The baseline's `noise_floor_stdev` is the *calibrated* variance, sampled at N=5+ when the operator explicitly invoked `calibrate`. Folding the current run's stdev into the ratchet predicate would let a freak quiet run permanently lower the noise floor, defeating the safeguard.
- **Git-tracked baselines = release-over-release diff in PRs.** Storing baselines under `benchmarks/baselines/` (not in `results/`, which is git-ignored) means every ratchet shows up in the PR diff and is reviewable. The author cannot silently raise the bar.
- **`no_baseline` is non-blocking.** New scenarios should not block CI before they are calibrated. The `no_baseline` classification preserves the pre-existing exit-0 behaviour for unpinned scenarios.
- **Manual `compare` survives unchanged.** Two operators may still want to diff arbitrary aggregate pairs (e.g. release-over-release post-mortem). That command keeps its exit-0 contract; only the new `run`-time path can fail the build.

## Alternatives considered

### Alternative 1: One-shot diff against a single pinned aggregate (no stdev)

Add `benchmarks compare-baseline <scenario_id>` that diffs the latest aggregate against a single pinned reference, range-based, no stdev. Hand-runs every PR.

Rejected because: it does not surface a verdict in `run`'s exit code, so CI cannot block on it; it inherits today's "noise vs signal" ambiguity wholesale; and it still requires the operator to remember to compare.

### Alternative 2: Pin temperature first; skip stdev modelling

Block this change behind Phase 3 (engine-temperature pinning), then gate on strict mean comparison.

Rejected because: pinning temperature is non-trivial and would push the release-gate work by a milestone. Modelling variance is the cheaper, sooner intervention and remains useful even after temperature is pinned (small residual variance survives).

### Alternative 3: Hard-coded thresholds (e.g. `current.mean < 0.8 * baseline.mean → regression`)

Skip stdev altogether; use a fixed fractional drop as the regression rule.

Rejected because: it does not scale across scenarios with different `total_base` values, and it is degenerate at the noise floor — a small-base scenario rolls past the threshold on every flip, while a large-base scenario hides real regressions. Calibrated stdev is the right per-scenario unit.

### Alternative 4: Auto-pin every successful main-branch run (no human gate)

Have CI auto-pin after every green merge to main.

Rejected because: it ratchets silently on every noise bounce that happens to land above the threshold, and it removes the PR-review checkpoint where a baseline change is visible in the diff. The `--update-baselines-on-improvement` flag is opt-in and lives behind an explicit CLI invocation.

## Consequences

Positive consequences:
- `benchmarks run` is now a usable CI gate for narrative regressions, not an eyeball job.
- Calibrated `noise_floor_stdev` is preserved across ratchets — a one-time `calibrate` investment pays off until the engine pin posture changes.
- Every baseline change is visible in the PR diff because `benchmarks/baselines/` is git-tracked.
- The `--no-compare` flag preserves the legacy "just run and observe" workflow for exploratory hacking.

Tradeoffs / risks:
- New scenarios will silently produce `no_baseline` until pinned — operators must remember to pin (or accept that the scenario is observational only).
- The 2-sigma ratchet predicate is intentionally conservative; large legitimate gains may take two ratchet cycles to fully absorb.
- `calibrate` is paid (hits real LLMs); operators must invoke it deliberately. CI never does.
- The auto-compare verdict assumes the same engine model set is in effect on both sides; switching `DIRECTOR_MODEL`/`NARRATOR_MODEL` without re-calibrating will mis-attribute variance as drift. The baseline carries `engine_models` for future drift-detection but does not currently block on mismatch — that is a Phase 3 follow-up.

What future agents must preserve:
- **The ratchet predicate is `delta > 2 * noise_floor_stdev`, strict `>`.** Do not lower the multiplier without superseding this ADR; do not switch to the current run's stdev.
- **`noise_floor_stdev` belongs to the baseline, not the aggregate.** It is set at pin/ratchet time from `calibrate`, never overwritten by a regular run.
- **`benchmarks calibrate` never runs on CI.** It is opt-in CLI-only because it hits paid LLMs.
- **`no_baseline` must not exit 1.** Unpinned scenarios are non-blocking by design.
- **Baselines live under `benchmarks/baselines/` and are git-tracked.** Do not move them to `results/` (git-ignored) — the PR-diff visibility is the human review checkpoint.
- If you supersede this ADR (e.g. once engine temperature is pinned and the noise floor collapses), preserve the exit-1-on-regression contract in `benchmarks run`; that is the user-visible release gate.

## Verification / tests

- `tests/test_benchmarks_aggregate.py::TestAggregateReports::test_stdev_population` asserts population stdev over `iteration_totals`.
- `tests/test_benchmarks_classify_stdev.py` covers the k-sigma overlap rule for regression / improvement / noise / equal-mean / zero-stdev / variable k.
- `tests/test_benchmarks_baselines.py` round-trips `PinnedBaseline` through `write_baseline` + `read_baseline` and asserts the metadata header is top-level.
- `tests/test_benchmarks_auto_compare.py` exercises `Verdict`, `any_regression`, `should_ratchet` (including the strict `>` boundary, the `improvement`-only gate, and the `noise_floor_stdev=0` block).
- `tests/test_benchmarks_run_auto_compare.py` asserts `auto_compare_exit_code` returns `1` on regression and `0` on noise/improvement/no_baseline; and that `--update-baselines-on-improvement` ratchets above-threshold improvements while leaving sub-threshold improvements untouched.
- `tests/test_benchmarks_pin.py` covers the calibration-noise-floor-preference rule and the scenario-id-mismatch guard.
- `tests/test_benchmarks_calibrate.py::TestPersistCalibration::test_high_noise_warning` asserts the `stdev > 0.15 * total_base` warning surfaces an `--iterations 10` recommendation.
- Coverage on the new modules is ≥99% under `--cov=benchmarks.cli._auto_compare,benchmarks.harness.baselines,...`.
