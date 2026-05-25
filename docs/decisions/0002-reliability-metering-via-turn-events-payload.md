# ADR-0002: Reliability counters persist on the turn_events.payload channel, not ai_call_logs

Date: 2026-05-25
Status: Accepted
Decision owner: Max
Related: GitHub issue #272 ("reliability: count silent fallbacks and validation retries"), `cast/_reliability_metrics.py`, `engine/session_ops.py`, `db/tables.py`

## Context

Several cast agents wrap risky paths in `except Exception: log + return fallback`. Dramaturge falls back to the unrewritten narration, Narrator falls back to an empty visible-entities list, DataMiner returns `None` from `ensure_fact`, Director silently swallows scene-consolidation failures, and the validation-retry loop in `_send_json` overwrites its own call-log entry each attempt. Failures are logged but never *counted*, so we cannot answer "how often does production silently degrade?" without grepping log archives.

Issue #272 adds per-turn metering (no behaviour change) so phase 2 can decide which silent fallbacks to actually harden. The spec mandated "no DB migration; piggyback on existing column" — but the table the spec named (`ai_call_logs`) has only typed columns (`agent_name`, `model`, `system_prompt`, `messages`, `response_content`, `prompt_tokens`, `completion_tokens`, `duration_ms`, `call_sequence`, `parent_agent`) and no JSON blob for arbitrary extras. Satisfying "no DB migration" forces us off `ai_call_logs`.

## Decision

Persist per-turn reliability counters as a `record_turn_event("reliability_snapshot", {counters: [...]})` entry written into the existing `turn_events.payload` (JSONB) column at the turn boundary.

- The in-process counter map lives in `cast/_reliability_metrics.py` on a `contextvars.ContextVar[dict[(agent, event_type), int] | None]`, mirroring the `call_log_buffer` pattern in `llm/call_logger.py`. No `threading.Lock` — asyncio is single-threaded; sibling-task increments inside one turn share the mutable map intentionally and per-turn reset bounds the blast radius.
- `engine/session_ops._bind_session_buffers` resets the counter map at the start of every turn alongside the AI-log and turn-event buffers.
- `engine/session_ops.persist_engine_state` snapshots the counters via `record_turn_event` *before* `get_and_clear_events` runs, so the snapshot rides the existing `turn_events.save` save path without a new repository method.
- Benchmark runs (no DB) capture the same snapshot on `ScenarioReport.reliability_counts` (new optional field, default `{}`) and persist it inside the per-iteration JSON archive that `archive.write_report` already produces.
- A new `benchmarks reliability-report <path>` subcommand walks per-iteration archives and prints a `(agent, event_type) → count` table.

## Rationale

- **`turn_events.payload` is JSONB and already designed for typed event payloads with a discriminator.** Its existing producers (`dice_contest`, `item_list`, …) use `record_turn_event("<type>", {arbitrary_dict})`, exactly the shape we need. The save path already exists, the admin dashboard already reads it, and a new `event_type="reliability_snapshot"` value is the smallest legible addition.
- **`ai_call_logs` is per-LLM-call.** Even if we added a JSON column there, the granularity is wrong — counters are per-turn, not per-call. Putting them on the LLM-call row would either duplicate the same blob N times per turn or arbitrarily attach it to one call.
- **Metering only — phase 2 acts on the data.** Adding migrations now would couple this PR to a schema decision the data should drive. The piggyback channel is reversible; a future `reliability_counters` table can read history out of the `turn_events` archive if it pays off.
- **One byte-identical narration test holds the line.** The load-bearing assertion that this is metering-only is `tests/test_reliability_metering_inert.py`: a Narrator turn runs once with metering buffer initialised, once torn down, asserting the produced string is byte-identical. Any future change that lets metering mutate narration breaks that test loudly.

## Alternatives considered

### Alternative 1 (spec wording): attach `reliability` extra field to the `ai_logs` payload

What the issue body literally said. Rejected because `ai_call_logs` has no JSON blob column to piggyback on, only typed columns — satisfying the spec literally would have required a migration, contradicting its own "no DB migration" constraint. The spec's "ai_logs payload" wording was best-read as "any existing persistence channel"; `turn_events.payload` is the only one with the right shape. Noted in the PR description.

### Alternative 2: new `reliability_counters` table

Cleanest long-term home. Rejected for phase 1: schema changes ahead of the data is exactly the coupling the issue body warns against ("phase 2 will use the resulting data to decide which silent fallbacks to actually replace"). A future ADR can promote the JSONB blob to a typed table once we know which counts matter and which never fire.

### Alternative 3: add the counter columns to `ai_call_logs`

Per-call columns (e.g. `did_fallback BOOLEAN`, `retry_count INT`) attached to whichever LLM call happened to fire last. Rejected: counters are turn-scoped, not call-scoped — there's no single call to attach them to. A `dramaturge` consistency-pass fallback fires after the Dramaturge LLM call already wrote its own log row; bolting the counter onto that row mixes two semantic levels.

## Consequences

Positive consequences:

- No migration; reversible.
- `turn_events` admin-dashboard surface picks up reliability snapshots for free.
- Benchmark archives carry the same blob under `ScenarioReport.reliability_counts`, so the new CLI works on the existing `benchmarks/results/` layout without re-running scenarios.
- The byte-identical narration test makes future regressions in this metering boundary visible at unit-test time.

Risk / what future agents must preserve:

- **`record_fallback` / `record_retry` are observation only.** Adding any control-flow effect to the recorders (e.g. raising on threshold breach) silently breaks the phase-1 contract; gate any such change behind a new ADR.
- **Counter cross-contamination across `asyncio.gather` siblings inside one turn is intentional.** asyncio is single-threaded, per-turn reset bounds blast radius; do not add locks or per-task isolation without a separate decision.
- **The four-value `EventType` literal includes `judge_error` with no recorder defined.** Reserved for phase 2 — do not delete it from the type alias without that ADR.

## Verification

- `tests/test_reliability_metrics.py` — counter map mutates correctly, snapshot is independent of further mutations, recorders no-op outside an initialised buffer.
- `tests/test_session_ops_reliability.py` — consumer-seam test: `persist_engine_state` writes a `reliability_snapshot` turn-event with the expected payload, and `_bind_session_buffers` resets the counter map.
- `tests/test_reliability_metering_inert.py` — byte-identical narration with metering on vs off.
- `tests/test_benchmarks_reliability_report.py` — CLI sums per-iteration archives and prints the `(agent, event_type)` table; aggregate archives are skipped.

## Future-agent guardrails

- Phase 2 (acting on the data) needs its own ADR — pick the threshold, the replacement strategy, and where the decision lives before changing any fallback site's behaviour.
- If counter shape grows (per-turn duration, per-attempt LLM latency, …), promote `turn_events.payload[counters]` from a list-of-rows to a typed schema in a follow-up ADR rather than versioning the JSON in place.
- Do not relocate the snapshot call out of `persist_engine_state` without preserving the "before `get_and_clear_events`" ordering — moving it after the flush silently drops the snapshot.
