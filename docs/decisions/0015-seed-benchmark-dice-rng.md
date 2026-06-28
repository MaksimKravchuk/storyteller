# ADR-0015: Seed the dice RNG in benchmark mode

Date: 2026-06-22
Status: Accepted
Decision owner: Storyteller engineering
Related: ADR-0003 (engine temperature pinning), ADR-0009 (CI benchmark comparison), ADR-0013 (Bayesian comparison), `cast/dice.py`, `benchmarks/harness/runner.py`, PR #327

## Context

The benchmark harness scores narration on curated scenarios and compares
"previous main → this PR" (ADR-0009/0013). ADR-0003 pins LLM temperature
so model sampling is as stable as possible, but **dice were never seeded**:
`cast/dice.py` rolled every contest with a fresh, unseeded
`random.Random()`. Combat/autonomy scenarios (`npc_autonomy_murder_plot`,
`escalation_guard_assault`, …) therefore drew different d20s on every run,
so the same code produced different clash outcomes → different narration →
the comparison flagged **false-positive regressions** unrelated to the
change under review. This surfaced on PR #327: scenarios the diff could not
touch (e.g. `scene_builder_re_entry_consistency`) regressed at P(reg) 100%,
proving the run, not the code, was the variable.

## Decision

Add an **installable seed base** to `cast/dice.py` and set it per scenario
iteration in the benchmark runner:

1. `cast/dice.py` gains `set_dice_seed_base(base)` plus `seed_task_dice(key)`,
   backed by two module-level `ContextVar`s (matching the codebase's
   swappable-state precedent in `llm/turn_event_logger.py`). `roll_contest` /
   `roll_aggression` draw from a base-seeded RNG when a base is installed, else
   a fresh `random.Random()` per roll.
2. `benchmarks/harness/runner.run_scenario_once` calls
   `set_dice_seed_base(_dice_seed(scenario.id, iteration))` before each run.
   `_dice_seed` is a stable `zlib.crc32` of `"{id}:{iteration}"` (not the
   per-process-salted built-in `hash`).
3. **Concurrency: per-task seeding.** NPC turns roll inside `asyncio.gather`
   (`cast.npc_turn`). Each gathered task copies the context, so a single shared
   RNG would let whichever LLM call finishes first consume the next d20 —
   non-deterministic by completion order. `cast.npc_turn._roll_npc_contest`
   calls `seed_task_dice(str(npc.uuid))` before rolling, giving each task its
   own RNG keyed on the NPC uuid (derived from the base), so contest outcomes
   are order-independent *and* distinct per NPC. Retaliation dice are rolled
   sequentially before its `gather`, so they need no per-task seeding.

Production never installs a base, so `seed_task_dice` is a no-op and live play
is byte-for-byte unchanged (fresh RNG per roll). The base is reset at the top
of every iteration, so there is no cross-iteration state bleed.

## Rationale

The seed depends only on `scenario.id` + `iteration`, so previous-main and
current-PR runs roll **identical dice** for the same scenario iteration —
dice luck cancels out of the delta, isolating real prompt/flow changes —
while dice still vary across iterations (so the rubric still samples a
spread of outcomes). This is the dice analogue of ADR-0003: pin the
controllable randomness so the comparison measures the change, not the RNG.

## Alternatives considered

### Alternative 1: Thread a seeded RNG through every call site

Pass `_rng=` from engine → director → npc_turn/ticker → dice. Rejected:
large, invasive plumbing through production hot paths for a harness-only
need; the install-a-default seam touches one module and leaves production
signatures untouched.

### Alternative 2: Seed Python's global `random`

`random.seed()` does not affect the `random.Random()` *instances* the dice
module creates, so it would not make rolls reproducible. Rejected.

### Alternative 3: Seed once per scenario (constant across iterations)

Simpler, but every iteration would roll identical dice, under-sampling
outcome variety. Seeding per (scenario, iteration) keeps the comparison
stable *and* samples dice across iterations.

### Alternative 4: Regenerate baselines instead

Re-pinning baselines hides the non-determinism rather than removing it, and
masks real regressions. Rejected in favour of fixing the root cause.

## Consequences

Positive consequences:
- Benchmark comparisons no longer flag dice-luck as regressions; the
  combat/autonomy scenarios become reproducible run-to-run.

Tradeoffs / risks:
- Residual LLM-sampling variance remains (temperature pinning is not
  perfect determinism); this ADR removes the *dice* source only.
- Concurrent NPC contests are made order-independent via `seed_task_dice`
  per-task seeding (decision 3). Any *new* concurrent dice site must call
  `seed_task_dice` with a stable key, or it will inherit a context-copied RNG
  and reintroduce completion-order dependence.
- The comparison is only fully apples-to-apples once both sides run the seeded
  flow; until this merges to main, "previous main" still rolls unseeded.

What future agents must preserve:
- Production must never install a seed base — keep `set_dice_seed_base` /
  `seed_task_dice` harness-only so live dice stay unseeded.
- Keep `_dice_seed` a stable hash (not built-in `hash`) so seeds reproduce
  across processes.
- Every concurrent dice site must `seed_task_dice` with a stable per-actor key.

## Verification / tests

- `tests/test_dice_default_rng.py`: same base reproduces the roll sequence;
  different bases diverge; the unseeded fallback stays in range; per-task
  seeding is order-independent for the same key and distinct across keys; and
  `seed_task_dice` is a no-op when unseeded.
- `tests/test_benchmarks_runner_seed.py`: `_dice_seed` is stable per
  (scenario, iteration) and varies by both.

## Related files

- `cast/dice.py`
- `benchmarks/harness/runner.py`
- `tests/test_dice_default_rng.py`
- `tests/test_benchmarks_runner_seed.py`
