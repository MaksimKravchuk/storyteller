# ADR-0016: Leave cold silent fallbacks unchanged until reliability data shows heat

Date: 2026-06-28
Status: Accepted
Decision owner: Storyteller engineering
Related: GitHub issue #273, ADR-0002, `cast/_reliability_metrics.py`, `benchmarks reliability-report`

## Context

ADR-0002 added observation-only reliability metering for several broad
`except Exception: log + return fallback` paths. The phase-2 question in
GitHub issue #273 was not "replace every fallback"; it was: after at least a
week of main-branch reliability data, replace or fix only the fallback sites
that actually fire often enough to matter (for example, >=1% of turns). Cold
sites should remain as-is.

The surveyed sites were:

- `cast/dramaturge.py` consistency-pass fallback.
- `cast/dramaturge.py` scene-dispatch enrichment fallback.
- `cast/dramaturge.py` scene-finalization enrichment fallback.
- `cast/narrator.py` visible-entities fallback.
- `cast/data_miner.py` `ensure_fact` fallback.
- `cast/director_execution.py` Dramaturge execution fallback.
- `cast/director_execution.py` scene-consolidation fallback.

A one-week survey of available successful `Benchmark baseline (main)` artifacts
showed no reliability counters for these sites. The concrete evidence used for
this decision was:

- Run `27949667592` on 2026-06-22 at commit
  `a66fd595f0df724207a654c293558493ec652067`: 11 scenario iterations, 40
  captured turns, all per-iteration `reliability_counts={}`.
- Run `28321003575` on 2026-06-28 at commit
  `185fbd0ca3025d5043841910c5c9a7aebf9e9b47`: 12 scenario iterations, 43
  captured turns, all per-iteration `reliability_counts={}`.
- `uv run python -m benchmarks reliability-report` over those downloaded
  artifacts printed `(no reliability counters found)`.

Across the surveyed 23 scenario iterations / 83 captured turns, every listed
fallback site classified as cold at 0/83 turns (0.0%).

## Decision

Do not introduce a `DegradedMode` contract, new caller-facing signal, or root
cause fix for issue #273 in this pass. Leave all seven surveyed fallback sites
unchanged because none reached the >=1% hot threshold in main reliability data.

Per-site decisions:

| Site | Metered key | Decision | Rationale |
| --- | --- | --- | --- |
| `cast/dramaturge.py` consistency pass | `dramaturge/silent_fallback` reason `consistency_pass` | Leave unchanged | No observed hits; returning raw Narrator prose remains a cold belt-and-braces fallback. |
| `cast/dramaturge.py` scene dispatch | `dramaturge/silent_fallback` reason `scene_dispatch` | Leave unchanged | No observed hits; this is post-narration enrichment for future turns. |
| `cast/dramaturge.py` scene finalize | `dramaturge/silent_fallback` reason `scene_finalize` | Leave unchanged | No observed hits; per-entity fact escalation is non-turn-critical enrichment. |
| `cast/narrator.py` visible entities | `narrator/silent_fallback` reason `visible_entities` | Leave unchanged | No observed hits; the fallback keeps narration alive if deterministic visible-entity collection breaks. |
| `cast/data_miner.py` `ensure_fact` | `data_miner/silent_fallback` reason `ensure_fact` | Leave unchanged | No observed hits; returning `None` is still a cold, best-effort research failure path. |
| `cast/director_execution.py` Dramaturge execute | `director/silent_fallback` reason `dramaturge_execute` | Leave unchanged | No observed hits; the Director should still return raw Narrator output rather than crash the turn for this cold guard. |
| `cast/director_execution.py` scene consolidation | `director/silent_fallback` reason `scene_consolidation` | Leave unchanged | No observed hits; scene-memory consolidation is enrichment and should not block turn completion while cold. |

## Rationale

Introducing `DegradedMode` would be a real product/API contract change: callers
would need to decide how to proceed, retry, or abort a turn. That may be the
right answer for a hot fallback, but it should be driven by evidence and a
separate contract design, not added speculatively to cold safety nets.

Leaving cold sites unchanged preserves the phase-1 promise from ADR-0002 that
metering is observation-only and narration remains byte-identical when no
failures fire. It also keeps graceful degradation intact: no cold fallback was
turned into a hard raise or a player-visible crash.

## Alternatives considered

### Alternative 1: Introduce `DegradedMode` for every listed site

Rejected. This would satisfy the letter of surfacing degradation, but it would
also create a broad new caller-facing contract without evidence that any listed
site fires in practice. It risks making stable cold guardrails more complex than
the failures they protect against.

### Alternative 2: Convert broad exceptions to raises

Rejected. The issue explicitly asks for visible degradation, not crashes. These
fallbacks exist to keep player turns alive when non-critical enrichment or
secondary review paths fail.

### Alternative 3: Keep only a PR description and no durable repo record

Rejected. The issue's immediate acceptance criterion asks for per-site decisions
in the PR description, but the project also relies on ADRs for future-agent
memory around architecture, evaluation, and player-facing behavior. A durable
ADR prevents a later agent from re-opening the same cold-site replacement work
without new reliability data.

## Consequences

Positive consequences:

- The phase-2 decision is data-driven: 0/83 captured turns means no site met the
  >=1% replacement threshold.
- Player turns continue to degrade gracefully on cold enrichment/review failures.
- No new `DegradedMode` API is introduced before there is a hot site that needs
  a concrete caller contract.
- Future agents have a durable record of why #273 closed without code-path
  replacements.

Tradeoffs / risks:

- The surveyed sample is limited to successful main benchmark artifacts still
  available from GitHub Actions. If future benchmark or production data shows a
  site crossing the threshold, this decision should be revisited.
- Cold today does not mean impossible; the existing reliability counters remain
  the guardrail for detecting future heat.
- Because no sites were replaced, no per-site `DegradedMode` regression tests
  were added in this pass.

What future agents must preserve:

- Do not add caller-visible degradation behavior for these fallback sites unless
  newer reliability data shows heat or logs identify a concrete root cause.
- Preserve `record_fallback` as observation-only unless a new ADR defines the
  control-flow contract and caller behavior.
- If any listed site reaches >=1% of turns in future `reliability-report` data,
  file a new decision choosing between `DegradedMode`, retry, abort, or a root
  cause fix for that specific site.

## Verification / tests

- Existing main benchmark-baseline artifacts were surveyed with
  `benchmarks reliability-report`; both successful runs printed
  `(no reliability counters found)`.
- No production code changed, so no new fallback behavior or `DegradedMode`
  regression tests were required for this pass.
- The phase-1 metering/inertness contract remains covered by
  `tests/test_reliability_metering_inert.py` and related reliability tests.

## Related files

- `docs/decisions/0002-reliability-metering-via-turn-events-payload.md`
- `cast/_reliability_metrics.py`
- `benchmarks/cli/_reliability_report.py`
- `tests/test_reliability_metering_inert.py`
- `tests/test_benchmarks_reliability_report.py`
