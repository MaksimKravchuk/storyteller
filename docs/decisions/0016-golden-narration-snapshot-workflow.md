---
type: Decision
title: "Golden narration snapshot workflow"
status: stable
governs:
  - benchmarks/baselines
  - tests/benchmarks/test_golden_narration.py
---
# ADR-0016: Golden narration snapshot workflow

Date: 2026-06-28
Status: Accepted
Decision owner: Storyteller engineering
Related: ADR-0002 (`docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`), ADR-0003 (`docs/decisions/0003-engine-temperature-pinning-in-benchmark-mode.md`), ADR-0009 (`docs/decisions/0009-ci-benchmark-version-comparison-comment.md`), ADR-0013 (`docs/decisions/0013-bayesian-benchmark-comparison-layer.md`), ADR-0015 (`docs/decisions/0015-seed-benchmark-dice-rng.md`), `benchmarks/golden/`, `benchmarks golden-update <scenario>`

## Context

Storyteller's narrative benchmark suite has two different review signals:

1. **Semantic scoring** from deterministic checks and the witness-panel rubric. This
   remains the primary signal for whether a narrative change is acceptable.
2. **Byte-exact narration snapshots** for scenarios where the benchmark input,
   model sampling, and provider model snapshot are pinned tightly enough that the
   expected prose should not move except when the engine behaviour changed.

The baseline re-pin workflow in ADR-0002 / ADR-0003 already treats score changes
as paid, explicit, human-reviewed updates to git-tracked references. Golden
narration snapshots need the same posture: useful when they catch accidental
prompt/output drift, dangerous when they are treated as a semantic judge or when
provider drift makes the bytes move for reasons outside this repository.

## Decision

Document and use `benchmarks/golden/<scenario_id>.json` as a **byte-exact
complement** to the benchmark score baselines, not a replacement for them.
Golden snapshots are appropriate only when all of the following are true:

- The scenario is stable and already worth protecting in PR review.
- Engine-side benchmark temperature is deterministic, normally via
  `BENCHMARK_TEMPERATURE_OVERRIDE=0.0` unless a more specific role override is
  intentionally documented.
- The provider and exact model snapshot are pinned strongly enough that the same
  prompt is expected to return identical bytes across runs. A generic model alias
  such as "latest" or a provider that silently changes the served checkpoint is
  not enough.
- Dice and other local randomness are controlled by the benchmark harness.
- The author has evidence that at least one repeat capture on the same code and
  provider snapshot is byte-stable.

Golden snapshot checks are intentionally narrower than witness-panel scoring:
they compare the captured narration bytes for a scenario against the committed
snapshot. They do not decide whether prose is good, coherent, or semantically
faithful. If the witness-panel score and a golden snapshot disagree, reviewers
should treat the witness-panel score and scenario rubric as the semantic signal,
and use the golden diff as a diagnostic pointer to inspect what changed.

## Workflow

### 1. Confirm prerequisites before creating or refreshing a snapshot

Before running a golden update, record the deterministic setup you used:

```bash
export BENCHMARK_TEMPERATURE_OVERRIDE=0.0
# Also pin provider/model snapshots through the project/provider configuration.
# Do not use floating aliases when generating committed golden snapshots.
```

In the PR, include the provider/model snapshot evidence, the temperature setting,
and a note that provider drift has been considered. If that evidence is missing,
do not commit a golden update; rely on the witness-panel benchmark report instead.

### 2. Run the local pytest guard

The pytest path is deterministic and does not require paid LLM calls when it is
only validating existing fixtures / no-golden behaviour:

```bash
uv run pytest tests/benchmarks/test_golden_narration.py -q
```

Use this before and after editing snapshots. The test should either pass against
committed `benchmarks/golden/*.json` files or skip clearly when no golden
snapshots are committed yet.

### 3. Capture or refresh exactly one scenario

Golden updates are explicit and per-scenario, like baseline pins:

```bash
BENCHMARK_TEMPERATURE_OVERRIDE=0.0 \
  uv run python -m benchmarks golden-update <scenario_id>
```

Example:

```bash
BENCHMARK_TEMPERATURE_OVERRIDE=0.0 \
  uv run python -m benchmarks golden-update narrator_prose_quiet_exploration
```

`golden-update` may invoke the live benchmark runner and can therefore hit paid
LLM/provider APIs. Run it only when cost/API-key approval exists. Commit only the
scenario snapshot(s) intentionally refreshed; do not sweep-update the whole
`benchmarks/golden/` directory unless the PR is explicitly a suite-wide re-pin.

### 4. Review the diff like a baseline re-pin

Golden snapshot PR language should mirror the baseline re-pin workflow:

- State whether this is a deliberate re-pin or an unexpected drift.
- Link or describe the code change that explains the narration byte change.
- Include prerequisite evidence: temperature override, provider, exact pinned
  model snapshot, scenario id, command run, and repeatability check.
- Use baseline-style review language, for example:
  - "Golden snapshot re-pin for `<scenario_id>` after intentional narrator
    prompt change; witness-panel score remains non-regressing."
  - "Do not treat this as a quality ratchet; the witness-panel rubric remains
    the semantic gate."
  - "Provider/model snapshot evidence: `<provider>/<snapshot>` with
    `BENCHMARK_TEMPERATURE_OVERRIDE=0.0`; repeated capture was byte-stable."

A golden diff without the prerequisite evidence is not reviewable. Either remove
the updated snapshot from the PR or mark the task as needing a paid/deterministic
rerun with pinned provider evidence.

## Warnings

- **Provider drift is real.** Temperature pinning does not freeze hosted model
  weights, safety layers, tokenizer behaviour, or infrastructure-side prompt
  handling. If a provider silently changes the served model, golden snapshots can
  fail while the Storyteller code is unchanged.
- **False positives are expected when prerequisites are loose.** Golden
  snapshots are byte-exact; harmless punctuation, whitespace, model phrasing, or
  provider-side changes can trip them. Treat failures as inspection prompts, not
  automatic semantic regressions.
- **Witness-panel scores remain primary.** Golden snapshots are a regression
  microscope for deterministic prose bytes. The witness-panel rubric and
  deterministic scenario elements remain the primary narrative-quality signal.
- **Golden updates are paid unless proven otherwise.** `golden-update` captures
  live scenario output through the benchmark runner, so it must follow the same
  explicit approval rules as other benchmark commands.

## What future agents must preserve

- Keep `benchmarks/golden/` git-tracked when snapshots exist so byte changes are
  visible in PR diffs, just like `benchmarks/baselines/`.
- Keep golden snapshot generation explicit and per-scenario. Do not auto-update
  golden snapshots from CI or from regular `benchmarks run`.
- Keep the pytest path deterministic and offline-friendly when validating
  committed snapshots.
- Keep PR review language clear that a golden re-pin is a byte-exact reference
  update, not a semantic quality ratchet.

## Verification / tests

- `tests/benchmarks/test_golden_narration.py` validates committed golden
  snapshots when present and skips clearly when no `benchmarks/golden/` fixtures
  exist.
- `benchmarks golden-update <scenario_id>` captures a scenario through the
  benchmark runner and writes `benchmarks/golden/<scenario_id>.json`; this path
  may hit paid LLM/provider APIs and is intentionally not part of routine CI.
