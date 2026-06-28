# 0003 — Engine-side temperature pinning in benchmark mode

- Status: accepted
- Date: 2026-05-26
- Issue: [#278](https://github.com/MaksimKravchuk/storyteller/issues/278)

## Context

`benchmarks/harness/judge.py` has pinned judge temperature at 0.0 for some
time, but the *engine* itself (Director, Actor, Narrator, SceneBuilder,
NPCGenerator, Dramaturge) ran at whatever temperature each `ModelConfig`
carried (default 0.7). On identical scenarios, narration therefore varied
run-to-run; PR #285 absorbed that variance into the per-scenario
`noise_floor_stdev` baseline, but it remained noise we don't have to live
with — and the wider the noise floor, the smaller a real regression has to
be before auto-compare lets it slip through.

## Decision

Introduce a **benchmark-mode-only** temperature override:

- `BENCHMARK_TEMPERATURE_OVERRIDE=<float>` pins every engine role's
  temperature.
- `BENCHMARK_<ROLE>_TEMPERATURE=<float>` (with `ROLE ∈ {DIRECTOR, AGENT,
  NARRATOR, DRAMATURGE}`) pins one role; per-role wins over global.
- When neither var is set, every role keeps the temperature its
  `ModelConfig` carries.

The override is read from env *only inside the benchmark harness's
`_prepare_engine`* (`benchmarks/harness/_run_execution.py`). The engine
factory accepts a `temperature_override: dict[str, float] | None` kwarg
and applies it via `dataclasses.replace` on each role's `ModelConfig`.

`create_engine_from_state` does **not** accept the override — the
benchmark path calls `create_engine(temperature_override=...)` followed
by `engine.restore_session(...)` directly. This keeps the public restored-
game API narrow and reflects the constraint below.

## Rationale

- **Determinism reduces noise floor.** With temperature pinned at 0.0,
  identical scenarios should produce (nearly) identical narration. Once
  the baselines are re-calibrated against the pinned-temperature engine,
  auto-compare can catch smaller regressions.
- **Env-var contract, not config wiring.** Putting the override behind
  env vars keeps `config.py` and production code paths untouched. The
  override has zero effect when the vars are unset — production callers
  cannot accidentally trip it.
- **Harness-only entry point.** Only `_prepare_engine` calls
  `load_temperature_overrides()`. No engine internal reads the env var;
  the engine factory just takes a typed dict. Tests can mock the loader
  or the factory call directly.

## Constraints future agents must preserve

- **Production behaviour unchanged.** Any change to `create_engine` or
  `engine/factory.py` must preserve the property that, with the env vars
  unset, every role's `ModelConfig.temperature` is exactly the value the
  default ModelConfig carries. A regression test
  (`test_create_engine_no_temperature_override_is_noop`) asserts this.
- **The override is benchmark-scoped.** Do not call
  `load_temperature_overrides()` from `engine/`, `cast/`, or any production
  entry point. The only sanctioned reader is the benchmark harness.
- **Re-calibration is a follow-up step.** This PR does not re-pin
  baselines. The acceptance criterion "stdev drops by ≥50% across
  iterations" requires a live run against paid LLMs; the operator runs
  `BENCHMARK_TEMPERATURE_OVERRIDE=0.0 uv run python -m benchmarks
  calibrate --iterations 5` and pins per-scenario baselines via
  `benchmarks pin <scenario> --from <aggregate.json>` (the workflow
  established by ADR-0002 / benchmark-auto-compare-and-ratchet).
- **Provider drift remains.** Even with temperature pinned, providers
  silently update underlying models. Golden narration snapshots are viable
  only when provider model snapshots are pinned and review evidence is
  documented; see ADR-0016 for the golden snapshot workflow and warnings.

## Alternatives considered

1. **Set temperature globally via `config.py`.** Rejected: would change
   production behaviour and require operators to know to flip the flag
   off in production. Env-var-only avoids the coupling.
2. **Engine reads env var internally.** Rejected: spreads the benchmark
   contract into production code paths; harder to test that the env var
   doesn't leak.
3. **Use a dataclass `BenchmarkOptions` passed to `create_engine`.**
   Future option if more benchmark-only knobs accumulate. For now, a
   single typed dict is enough.

## Consequences

- Once an operator runs the calibration + re-pin workflow with the
  override set, the `noise_floor_stdev` field in each pinned baseline
  drops, and the auto-compare regression band tightens. PRs touching
  narrative-affecting code (#277) get a finer regression signal.
- Production runs continue at config-default temperatures. Players see
  the same narrative variance they did before this PR.

## Verification

- Unit tests: `tests/benchmarks/test_temperature_override.py` (env-var
  parsing) and `tests/benchmarks/test_temperature_override_seam.py`
  (consumer-seam — env → factory kwarg).
- Engine factory tests: `tests/test_engine_factory.py`
  (`test_create_engine_applies_temperature_override`,
  `test_create_engine_partial_temperature_override`,
  `test_create_engine_no_temperature_override_is_noop`).
- Local gauntlet: ruff, ruff format, flake8, mypy, pytest all green;
  90.58% coverage.
