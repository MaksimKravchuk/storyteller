---
type: Decision
title: "Bayesian benchmark-comparison layer + wider judge panel + deterministic landmark conversion"
status: stable
governs:
  - benchmarks/harness/bayes
  - benchmarks/cli/_bayes_report.py
  - benchmarks/cli/_bayes_format.py
  - .github/workflows/benchmark-on-pr.yml
  - benchmarks/scenarios/scene_builder_re_entry_consistency/elements.py
  - benchmarks/harness/panel.py
  - tests/test_benchmarks_bayes.py
  - tests/test_benchmarks_bayes_cli.py
  - tests/test_benchmarks_scene_builder_predicate.py
  - tests/test_benchmarks_aggregate.py
  - tests/test_benchmarks_pin.py
  - benchmarks/cli
  - benchmarks/harness/bayes/__init__.py
  - benchmarks/harness/bayes/_types.py
  - benchmarks/harness/bayes/_normal.py
  - benchmarks/harness/bayes/_beta.py
  - benchmarks/harness/bayes/_beta_quadrature.py
  - benchmarks/harness/bayes/_report.py
  - benchmarks/cli/_compare.py
  - benchmarks/cli/_args.py
  - benchmarks/cli/_pin.py
  - benchmarks/harness/aggregate.py
  - benchmarks/harness/types/_aggregates.py
  - benchmarks/harness/_baselines_codec.py
  - .github/workflows/noise-floor-recalibration.yml
  - .github/workflows/benchmark-baseline.yml
---
# ADR-0013: Bayesian benchmark-comparison layer + wider judge panel + deterministic landmark conversion

Date: 2026-06-20
Status: Accepted (roster composition in Decision 1 superseded by ADR-0019; the odd cap and everything else stand)
Decision owner: Max
Related: ADR-0002 (`docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`), ADR-0003 (`docs/decisions/0003-engine-temperature-pinning-in-benchmark-mode.md`), ADR-0009 (`docs/decisions/0009-ci-benchmark-version-comparison-comment.md`), `benchmarks/harness/bayes/`, `benchmarks/cli/_bayes_report.py`, `benchmarks/cli/_bayes_format.py`, `.github/workflows/benchmark-on-pr.yml`, `benchmarks/scenarios/scene_builder_re_entry_consistency/elements.py`

## Context

ADR-0002 turned `benchmarks run` into a regression gate with a two-tier verdict: at `iterations >= 3` it uses a k-sigma overlap test against the calibrated noise floor; at `iterations < 3` it falls back to a plain range-overlap classifier (`classify_range`). ADR-0009 made the PR comment advisory and pinned the CI run at `--iterations 1 --max-judges 3` to keep per-PR LLM spend at ~$0.02–$0.10.

The combination is the problem. At `N=1` the range-overlap classifier has no statistical power: with a single current observation there is no spread to overlap, so the PR comment reports **"noise" for essentially every scenario regardless of how the prose actually moved**. The headline verdict a reviewer reads before merging a narrative PR is therefore uninformative on the exact runs (PR pushes) where it is supposed to help. ADR-0003 pinned engine temperature, which collapses *engine* variance — but the dominant residual noise source on a single transcript is now **judge variance**: a 3-judge panel splits 2–1 often enough that one element's pass/fail flips between runs for reasons unrelated to the engine change under test.

Three structural facts shaped the fix:

1. **The cheap axis is judge votes, not engine iterations.** Re-running the multi-agent engine to get a second iteration is expensive (full Director→...→Narrator turn chain per iteration). Adding judges to a single fixed transcript is cheap (one dispatch call per judge per evidence element) and directly attacks the dominant residual noise. Spending on judges buys more statistical resolution per dollar than spending on iterations.
2. **One "evidence-LLM" element was never actually subjective.** In `scene_builder_re_entry_consistency`, the element `prose_consistent_on_return` asked judges whether the re-entry narration mentions a seeded Forum landmark — a closed-set membership test over the fixed `FORUM_POIS` set. The judges agreed on it every time; paying six judges to confirm a substring match is waste and adds judge-variance noise to a fact that has none.
3. **The frequentist gate is load-bearing and must not be weakened.** ADR-0002's exit-1-on-regression contract (and ADR-0009's advisory-comment posture over it) is the release safety mechanism. Any new reporting must *augment* the verdict, not replace the gate.

## Decision

Three coupled changes, all additive to the ADR-0002/ADR-0009 mechanism, all pure-stdlib and deterministic.

1. **Widen the PR judge panel from 3 to an odd 5.** `benchmark-on-pr.yml` now runs `benchmarks run --iterations 1 --max-judges 5`. The `DEFAULT_ROSTER` carries six candidates (3 Anthropic: opus/sonnet/haiku, 3 OpenAI: gpt-5.4/-mini/-nano); the cap of 5 fields the first five when both API keys are present (`benchmarks/harness/panel.py` keeps `DEFAULT_MAX_JUDGES = 6` as the "use the full roster" ad-hoc default — the CI scoring paths pin the cap explicitly). This spends on the cheap judge axis rather than the expensive engine-iteration axis: a wider panel beats down judge variance — the dominant residual noise once engine temperature is pinned (ADR-0003) — without re-running the engine. Two constraints make this correct rather than merely wider:
   - **The cap is odd (5, not 6).** With an even panel an evidence element can split 3–3, and `_evidence_awarded` returns `round(base_value * 3/6)`, which is `round(0.5) == 0` for a 1-point element — so an even panel would add a *downward bias* on tied 1-point elements instead of only reducing variance. An odd cap cannot split evenly (barring a judge error reducing the live count).
   - **The cap must be identical across `benchmark-on-pr.yml`, `noise-floor-recalibration.yml`, and `benchmark-baseline.yml`.** The Bayesian delta uses the pinned `noise_floor_stdev` as the variance scale for PR results; a noise floor calibrated on a different (noisier) panel would mis-scale every reported probability and credible interval. All three now run `--max-judges 5`.

2. **Convert the one assertable evidence element to a deterministic landmark-membership test.** `prose_consistent_on_return` (label kept: "Re-entry narration mentions at least one seeded Forum landmark") is now a `KIND_DETERMINISTIC` element whose check `_re_entry_names_landmark` tests the re-entry turn's narration for any seeded `FORUM_POIS` landmark — no judge, zero LLM cost, zero judge-variance noise. Matching is **alias-aware** (`_LANDMARK_ALIASES`): each landmark carries its canonical name plus common paraphrases ("Saturn's temple" for the Temple of Saturn, "the speakers' platform" for the rostra), because the old evidence prompt recognised those and an exact-primary-name-only check would flag a valid paraphrase as a false regression. The genuinely subjective question (does the re-entry prose *contradict* the first visit's atmosphere) stays an evidence-LLM element (`no_contradictory_redescription`).

3. **Add an additive Bayesian reporting layer (`benchmarks/harness/bayes/`).** It produces graded posteriors alongside the unchanged frequentist verdict:
   - **Per-scenario total delta — conjugate Normal.** Each scenario total is a draw from `Normal(mu, sigma^2)` where `sigma` is the baseline's calibrated `noise_floor_stdev`. With a flat prior the delta `current.mean - baseline.mean` is Normal with standard error `sqrt(noise_floor_stdev^2 * (1/n_base + 1/n_cur))`. **This yields a graded P(regression)/P(equivalent)/P(improvement) and a 95% credible interval from a single current iteration**, because the baseline supplies the noise scale — no engine re-run required. The three probabilities are the posterior masses below `-rope`, inside the ROPE, and above `+rope` (`DEFAULT_ROPE = 0.5` score-points).
   - **Per-element drill-down — Beta-Binomial over retained judge votes.** Each evidence element's YES/NO votes are Binomial; with a `Beta(1,1)` prior the pass-probability posterior is `Beta(1+yes, 1+no)`, and `P(theta_current < theta_baseline)` is computed by deterministic trapezoid quadrature (`_beta_quadrature.prob_below`, 1000-step grid — no special-function dependency). **Resolution prefers judge votes (`k_yes`/`n_votes`), falls back to iteration pass-counts, then a flat prior** — so a wider panel automatically tightens this posterior with no extra iteration.
   - **Pooled portfolio bias.** Summing the independent scenario-total deltas into one Normal posterior gives `P(suite worse)/P(eq)/P(suite better)` — a systematic-shift signal **no single noisy scenario can show on its own** (e.g. every scenario drifts down by a fraction of a point: individually noise, collectively a regression).

   Surfaced via a new offline subcommand `benchmarks bayes-report <results_dir>` (reads `*_aggregate.json`, compares each to its pinned baseline, prints per-scenario + portfolio lines; pure file IO, no engine run, no LLM calls), and inlined beneath the frequentist banner in `benchmarks compare`. The PR workflow posts the `bayes-report` block in the advisory comment.

**The frequentist gate is unchanged.** ADR-0002's k-sigma / range classifier still drives the `[auto-compare]` verdict and the CLI exit code; ADR-0009's advisory posture over it is untouched. The Bayesian layer is read-only reporting — it has no exit code and gates nothing. This is augmentation, not replacement.

**The aggregate schema is backward-compatible.** `ElementPassRate` gains `k_yes: int = 0` and `n_votes: int = 0` (defaulted), serialised/deserialised with `.get(..., 0)` in `_baselines_codec.py`. Baselines pinned before judge tallies were retained still load; the Beta-Binomial silently falls back to iteration pass-counts for them.

## Rationale

- **N=1 range-overlap is structurally powerless; a noise-floor-scaled Normal is not.** The range classifier needs spread it does not have at one iteration. Borrowing the calibrated `noise_floor_stdev` from the baseline gives the single current observation a variance scale, which is exactly what is needed to grade confidence without paying for a second engine run. This is the cheapest way to make the N=1 PR comment say something true.
- **Graded beats binary for a reviewer.** "noise" vs "regression" forces a hard call on a fuzzy signal. `P(regression)=0.82 [95% CI −1.4, +0.1]` tells a reviewer both the direction and how sure to be — the right shape for an *advisory* comment a human reads before merging.
- **Spend on the axis with the most noise per dollar.** Post-ADR-0003, engine variance is pinned and judge disagreement dominates residual noise on a single transcript. Five judges over one transcript cuts that variance far more cost-effectively than a second (or third) full engine iteration would, and the Beta-Binomial turns those extra votes directly into a tighter per-element posterior.
- **Don't pay judges for facts.** An alias-aware membership test over a fixed landmark set is deterministic by construction. Moving it out of the panel removes both its cost and its judge-variance contribution, and makes that signal perfectly reproducible.
- **The portfolio line catches the failure class no per-scenario verdict can.** A uniform small downward drift across the suite is individually indistinguishable from noise but collectively a real regression. Pooling the deltas is the only place that shows up.
- **Pure stdlib + deterministic keeps it unit-testable and CI-safe.** No new dependency, no RNG, no LLM in the Bayesian layer — it is exercised by sync unit tests and runs identically every time, so it can live inside the advisory CI comment without adding flakiness or paid calls.
- **Augment, never replace, preserves the release safety net.** The frequentist exit-1 gate is the thing branch protection (in any non-path-filtered context) can hang a required check on. Leaving it byte-for-byte intact means this change carries zero risk to the gate's behaviour.

## Alternatives considered

### Alternative 1: Raise PR iterations from 1 to 3 (buy power on the engine axis)

Run `--iterations 3` on PRs so the existing k-sigma classifier (ADR-0002) regains power at the `iterations >= 3` tier, no new statistics needed.

Rejected because it triples the most expensive axis — three full multi-agent engine turn-chains per scenario per PR push — to fix a noise source (judge disagreement) that extra iterations address only indirectly. After ADR-0003 pins engine temperature, additional iterations mostly re-sample judge variance anyway; widening the panel attacks that variance directly and far more cheaply. It also leaves the N=1 case (still used by `benchmark-baseline.yml` and any future cheap run) powerless.

### Alternative 2: Replace the frequentist verdict with the Bayesian one

Drive the `[auto-compare]` verdict and the CLI exit code from `P(regression)` (e.g. exit 1 when `P(regression) > 0.95`).

Rejected because it rewrites the ADR-0002 release gate — the load-bearing safety mechanism — to fix a *reporting* problem. The two answer different questions (a calibrated frequentist threshold vs a graded posterior) and a reviewer benefits from both. Changing the gate's exit semantics is a far larger blast radius than the problem warrants; the Bayesian layer is purely additive precisely to avoid touching it.

### Alternative 3: Keep `prose_consistent_on_return` as an evidence-LLM element

Leave the landmark-membership check on the judge panel.

Rejected because the proposition is a deterministic substring test over a fixed set — the judges always agreed, so paying six of them adds cost and injects judge variance into a signal that has none. A deterministic check is cheaper, perfectly reproducible, and removes a noise contributor.

### Alternative 4: Sample-based Beta comparison (Monte Carlo `P(theta_c < theta_b)`)

Estimate the per-element regression probability by drawing from the two Beta posteriors and counting.

Rejected because it introduces an RNG and non-determinism into a layer that runs inside the CI comment. Deterministic trapezoid quadrature over a fixed 1000-step grid (`prob_below`) gives the same answer every run with no seed management and no dependency, which is required for a reproducible advisory comment and clean unit tests.

## Consequences

Positive consequences:
- The N=1 PR comment now carries a real, graded verdict (P-values + 95% CI) instead of a uniform "noise" non-answer.
- The portfolio-bias line surfaces a systematic suite-wide drift that no per-scenario verdict can detect.
- Per-element resolution improves automatically as the panel widens — the Beta-Binomial consumes the extra `k_yes`/`n_votes` directly.
- One landmark element is now deterministic: cheaper, reproducible, and noise-free.
- The Bayesian layer is pure stdlib and side-effect free, so it is fully unit-tested without hitting LLMs and adds no CI flakiness or paid calls.
- The aggregate schema change is backward-compatible: pre-tally baselines still load and degrade to the pass-count fallback.

Tradeoffs / risks:
- Per-PR LLM spend roughly doubles (~$0.04–$0.20 vs ~$0.02–$0.10) because of the 6-judge panel. This is the deliberate trade: spend on the cheap, high-information judge axis rather than the expensive engine-iteration axis. `concurrency: cancel-in-progress` still bounds it to the HEAD commit.
- The conjugate-Normal delta leans on the baseline's `noise_floor_stdev` as the noise scale. If a baseline's noise floor is stale or was never calibrated, the credible interval is mis-scaled. The `bayes-report` path uses the pinned `noise_floor_stdev`; the inline `benchmarks compare` path (which only has a jq-extracted aggregate, no separate noise floor) substitutes the baseline's own descriptive `stdev_awarded` — an approximation, noted in the code.
- **Full per-element resolution is not yet realized.** Pinned baselines from before this change carry `k_yes=0`/`n_votes=0`, so their elements fall back to coarse iteration pass-counts until main is re-pinned. Realizing the judge-level resolution requires the follow-up (below).

What future agents must preserve:
- **The Bayesian layer is additive reporting, never a gate.** It has no exit code and must not acquire one. The frequentist k-sigma/range classifier (ADR-0002) remains the sole driver of the `[auto-compare]` verdict and the CLI exit code; ADR-0009's advisory posture over it is unchanged. Do not route the exit code through `P(regression)`.
- **Spend stays on the judge axis for PR runs.** The 3→5 panel widening is the intended cost posture: a wider panel over one fixed transcript, not more engine iterations. Do not "fix" cost by dropping back to 3 judges (re-strands the N=1 verdict) and do not bump PR iterations as the power fix.
- **The panel cap stays odd and identical across the three scoring workflows.** `benchmark-on-pr.yml`, `noise-floor-recalibration.yml`, and `benchmark-baseline.yml` must all use the same `--max-judges` value, and it must be odd — an even cap reintroduces the 3–3 `round(0.5)==0` downward bias on 1-point elements, and a mismatched cap mis-scales the noise floor the Bayesian delta divides by.
- **`prose_consistent_on_return` stays deterministic.** It is an alias-aware membership test; do not move it back onto the judge panel. Keep `_LANDMARK_ALIASES` covering the paraphrases the narrator actually uses so valid prose is not flagged as a false regression. The subjective half lives in `no_contradictory_redescription`.
- **The aggregate schema stays backward-compatible, and the pin path must carry the tallies.** `k_yes`/`n_votes` default to 0 and are read with `.get(..., 0)`; the Beta-Binomial must keep the judge-votes → pass-counts → flat-prior fallback chain so pre-tally baselines still load. `benchmarks pin` reuses the codec (`aggregate_from_dict`) precisely so a re-pin preserves the tallies; do not reintroduce a hand-rolled aggregate rebuild that drops them.
- **`bayes-report` scores one aggregate per scenario.** It deduplicates `*_aggregate.json` by `scenario_id` so an archive directory holding several runs per scenario does not double-count into the portfolio posterior.
- **The Bayesian layer stays pure stdlib and deterministic.** No RNG, no new dependency, no LLM call inside `benchmarks/harness/bayes/`. `prob_below` uses deterministic quadrature on a fixed grid; keep it that way so the advisory comment is reproducible.

## Follow-up

The judge-level per-element resolution is only fully realized once `main` is **re-pinned and recalibrated** with the wider panel: a calibration + `benchmarks pin` pass (the ADR-0002 / ADR-0003 workflow, with `BENCHMARK_TEMPERATURE_OVERRIDE=0.0`) writes baselines carrying `k_yes`/`n_votes` tallies, after which the Beta-Binomial drill-down runs at judge resolution instead of the iteration-pass-count fallback. Until that follow-up lands, pre-existing baselines degrade gracefully to pass-counts. This re-pin is paid (hits real LLMs) and is an explicit, human-gated step — never run on CI, consistent with ADR-0002.

## Verification / tests

- `tests/test_benchmarks_bayes.py` — the conjugate-Normal delta posterior (P-mass split around the ROPE, CI, zero/degenerate noise-floor and zero-iteration handling), the Beta-Binomial `prob_below` quadrature and `element_inferiority` resolution chain (judges → pass-counts → flat prior), and `pool_deltas` portfolio summation.
- `tests/test_benchmarks_bayes_cli.py` — the `bayes-report` subcommand (per-scenario block + portfolio line, `--rope`, no-pinned-baseline skip, missing results dir → exit 1, **and dedup: duplicate archive aggregates for one scenario count once**) and the `--rope` non-negative argparse type.
- `tests/test_benchmarks_scene_builder_predicate.py` — the deterministic `_re_entry_names_landmark` check (names a seeded landmark → awarded; **a paraphrased alias still awards**; names none → 0; re-entry turn not captured → 0).
- `tests/test_benchmarks_aggregate.py` / baseline round-trip tests — `k_yes`/`n_votes` tally accumulation in `aggregate_reports` and the `.get(..., 0)` backward-compatible codec round-trip; `tests/test_benchmarks_pin.py` asserts `benchmarks pin` carries the tallies into the written baseline.
- The ADR-0002 auto-compare / ratchet / baseline tests are *not* re-claimed here — they protect the frequentist gate this ADR augments, not the Bayesian layer this ADR adds.
- Local gauntlet (ruff, ruff format, flake8, mypy, pytest excluding e2e/benchmarks) must pass before commit — this branch carries new and modified Python across `benchmarks/harness/bayes/`, `benchmarks/cli/`, and the scenario rubric, not just the ADR.

## Related files

- `benchmarks/harness/bayes/__init__.py`
- `benchmarks/harness/bayes/_types.py`
- `benchmarks/harness/bayes/_normal.py`
- `benchmarks/harness/bayes/_beta.py`
- `benchmarks/harness/bayes/_beta_quadrature.py`
- `benchmarks/harness/bayes/_report.py`
- `benchmarks/cli/_bayes_report.py`
- `benchmarks/cli/_bayes_format.py`
- `benchmarks/cli/_compare.py` (inline Bayesian verdict beneath the frequentist banner)
- `benchmarks/cli/_args.py` / `benchmarks/cli/_dispatch.py` (`bayes-report` subcommand wiring)
- `benchmarks/harness/panel.py` (`DEFAULT_MAX_JUDGES = 6`, six-candidate roster; CI caps to an odd 5 explicitly)
- `benchmarks/cli/_pin.py` (reuses `aggregate_from_dict` so a re-pin preserves `k_yes` / `n_votes`)
- `benchmarks/harness/aggregate.py` / `benchmarks/harness/types/_aggregates.py` / `benchmarks/harness/_baselines_codec.py` (`k_yes` / `n_votes` tallies, backward-compatible codec)
- `benchmarks/scenarios/scene_builder_re_entry_consistency/elements.py` (alias-aware deterministic landmark-membership conversion)
- `.github/workflows/benchmark-on-pr.yml` (`--max-judges 5`, posts the `bayes-report` block)
- `.github/workflows/noise-floor-recalibration.yml` / `.github/workflows/benchmark-baseline.yml` (`--max-judges 5`, panel cap kept identical to the PR run)
- `tests/test_benchmarks_bayes.py`
- `tests/test_benchmarks_bayes_cli.py`
- `tests/test_benchmarks_scene_builder_predicate.py`
- `docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`
- `docs/decisions/0003-engine-temperature-pinning-in-benchmark-mode.md`
- `docs/decisions/0009-ci-benchmark-version-comparison-comment.md`
