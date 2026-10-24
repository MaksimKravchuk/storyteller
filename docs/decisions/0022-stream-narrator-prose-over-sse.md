# ADR-0022: Stream Narrator prose to the web player over SSE, moderated sentence by sentence

Date: 2026-10-25
Status: Proposed
Decision owner: Max (player-facing behavior; the merge needs Max's approval)
Related: [ADR-0006](0006-content-safety-moderation-pipeline.md) (moderation at the engine seam), [ADR-0002 reliability metering](0002-reliability-metering-via-turn-events-payload.md) (ContextVar-per-turn pattern), [ADR-0019 player UI](0019-player-ui-stage-visual-language.md), branch `feat/narrator-streaming`

## Context

Before this change, a player turn was one blocking `POST /api/games/{id}/actions`. The player saw a pending indicator until the whole pipeline finished: Director classification, clock advance, performers, Narrator, outbound moderation, and persistence. Only then did the full passage show up. The Narrator is the last LLM call and its prose is the only output the player reads, so the passage could be shown while it is still being written.

*Inferred:* the goal is perceived latency. The prose starts to appear as soon as the Narrator writes it, instead of after the full turn. The total turn time does not change.

Three constraints shaped the design:

1. **Outbound moderation (ADR-0006) must still apply.** Unmoderated prose must not reach the player, even briefly.
2. **The Dramaturge can rewrite a passage** after the Narrator drafts it (`DRAMATURGE_ENABLED`, off by default). If that draft streamed, the player would see text change after reading it.
3. **A turn costs money and changes game state.** Closing the tab mid-stream must not leave a half-done turn or throw away a paid one.

## Decision

Add `POST /api/games/{game_id}/actions/stream` (`interfaces/web/routes_stream.py`). It returns `text/event-stream` with these events:

- `stage` — a pipeline stage change: `acting` (Director starts executing the plan) and `narrating` (Narrator starts).
- `delta` — the next moderated chunk of Narrator prose.
- Exactly one terminal event:
  - `done` — the same `ActionResponse` that `POST .../actions` returns.
  - `error` — the HTTP status and detail that route would have returned. Unexpected exceptions become a generic 500 detail, so exception text never reaches the client.

The non-streamed `POST .../actions` route stays and behaves the same. The web player (`app.js`) now uses the stream route.

How it works:

- **Turn-scoped sink via ContextVar** (`llm/turn_stream.py`). This is the same pattern as `llm.call_logger` and reliability metering. The web layer binds a sink for one turn. Performers deep in the call tree send events to it without a callback threaded through every signature. When no sink is bound, every emit does nothing, so non-streamed turns, benchmarks, and tests are unchanged.
- **Only the Narrator streams.** `BasePerformer.streams_text` is `False` by default and `Narrator` sets it to `True`. `_send` switches to `llm_client.stream_message` only when a sink is bound and the performer opts in. Streaming is plain text only and takes no `output_format`.
- **Provider contract.** `BaseLLMClient.stream_message` falls back to one chunk holding the whole body, so any client or fake still satisfies it. `OpenAIClient` and `AnthropicClient` stream natively and return the same assembled `LLMResponse` as `send_message`. OpenAI retries only the opening of the stream, never a half-sent body.
- **Sentence-by-sentence outbound moderation at the engine seam.** `GameEngine.process_action` calls `engine.moderation.moderate_narration`. When a sink is bound, Narrator deltas pass through a `SentenceGate`:
  - The gate buffers text up to sentence boundaries (terminal punctuation plus closing quotes or brackets, or a line break).
  - It runs the outbound `Moderator.check` on each completed chunk before releasing it.
  - It flushes the unterminated tail when the Narrator finishes.
  - After the first flagged chunk, it releases nothing more and the whole passage becomes `fallback_narration`.
  - If no chunk is flagged, the **full passage still gets the regular outbound check**, because a passage can read worse than any one sentence in it.
  - With safety disabled (no moderator), deltas pass straight through.
- **Dramaturge-reviewed passages don't stream.** `PlanExecutor` passes `stream_live = dramaturge is None or scene is None`. The Narrator emits the `narrating` stage, then runs its LLM call inside `turn_stream.muted(...)`. The player sees the stage label and then the final passage in `done`, and never sees a draft that gets rewritten.
- **Dropped connections still finish and persist the turn.** `action_stream.stream_turn` runs the turn in its own task that writes to a queue. When the response generator closes, including when the client disconnects, its cleanup awaits that task inside `anyio.CancelScope(shield=True)`. The turn finishes, persists, and keeps the request-scoped DB session open until it is done. The client shows "Connection lost before the turn finished. Reload to see it."
- **Client rendering.** `app.js` shows streamed prose as plain text in a live passage, with markdown `*` markers removed. When `done` arrives, the server-rendered `narration_html` replaces it. That final text is authoritative, including when moderation replaced the passage. Stage events update the pending label. Response headers `Cache-Control: no-cache` and `X-Accel-Buffering: no` stop proxies from buffering the stream.

## Rationale

- **Moderation stays where ADR-0006 put it.** The gate runs inside `process_action`, not in the web route. Any future streaming surface gets sentence-level moderation by binding a sink and calling the engine. Checking each sentence before release is the smallest unit that keeps the "unmoderated prose never reaches the player" guarantee and still streams.
- **The final `done` payload is the source of truth.** Streamed deltas are only a preview. The persisted, rendered, fully moderated passage always replaces them. This keeps the stream route equivalent to the blocking route for state, persistence, and the response schema.
- **No streamed text gets rewritten while the player watches.** Muting the Dramaturge path costs only the latency benefit, and only when the opt-in Dramaturge is on. The default config streams.
- **Turns are paid, stateful work.** Cancelling on disconnect would waste the LLM spend and could leave the game state half-updated. Letting the turn finish matches what the blocking route already does when a client disconnects.
- **The ContextVar sink keeps the change narrow.** Agent signatures, prompt templates, and non-web callers do not change. This follows the call-logger and metering precedent instead of adding a new plumbing style.

## Alternatives considered

### Stream raw tokens and moderate only the finished passage

This is the simplest option and adds no per-sentence latency. It was rejected because flagged prose would reach the player's screen before the outbound check runs, which breaks ADR-0006.

### Moderate the whole passage first, then stream it

This keeps the single-check model. It was rejected because the Narrator has already finished by then, so streaming would only animate text that is already complete. The player gets no latency benefit.

### WebSocket, or a GET `EventSource`

A WebSocket is bidirectional and needs extra connection management, but a turn is one request and one response stream. `EventSource` only supports GET, which cannot carry the action body and the auth headers the player API uses (inferred). A POST that returns `text/event-stream`, read with `fetch` plus a stream reader, reuses the existing auth, error mapping, and request schema.

### Thread an `on_delta` callback through the Director, executor, and Narrator signatures

This makes the data flow explicit. It was rejected because it touches every intermediate signature and every test fake for a concern only the Narrator and the web layer need. The ContextVar pattern already exists for this kind of turn-scoped side channel.

### Stream the Dramaturge draft, then swap in the reviewed text

This would keep the latency benefit when the Dramaturge is on. It was rejected because the player would watch text they had already read change, which is worse than waiting.

### Cancel the turn when the client disconnects

This saves compute on abandoned turns. It was rejected because the LLM spend is already incurred mid-turn, and abandoning it can leave the game state partly applied. Finishing and persisting means a reload shows the completed turn.

## Consequences

Positive:

- The player sees Narrator prose as it is written, and stage labels while earlier stages run.
- The safety guarantee is unchanged: every released chunk passed outbound moderation, and the final passage passed the full-text check.
- Non-streamed callers (the blocking route, benchmarks, tests) behave exactly as before, because no sink is bound.
- Any provider client works. Clients without native streaming deliver the body as one chunk.

Tradeoffs and risks:

- **One moderation call per sentence plus one for the full passage**, instead of one per passage. Each check blocks the next release (the `shortcut:` comment in `SentenceGate._release`), so the stream can pause between sentences when the OpenAI moderation provider is keyed. If the pauses are noticeable, pipeline the checks.
- **Text can appear and then be replaced.** If a later sentence is flagged, or the full-passage check flags prose whose individual sentences passed, the earlier sentences were already shown. The `done` payload then replaces them with the fallback. Each sentence the player saw had passed moderation on its own, but the player can see a passage swapped for the fallback.
- **The live preview is plain text.** Markdown markers are removed rather than rendered until `narration_html` arrives, so the formatting can change when the preview is replaced.
- **A disconnected request keeps its DB session and task alive until the turn ends.** Many abandoned turns at once hold connections for the full turn time.
- Only the player-action turn (`process_action`) streams. The opening turn (`start_game`) still uses the blocking path.

What future agents must preserve:

- **Never release Narrator prose to a sink before it passes outbound moderation.** New streaming surfaces must go through `GameEngine.process_action` / `moderate_narration`. Do not bind a raw sink around the Narrator outside the gate.
- **Keep the full-passage outbound check** after a streamed passage with no flagged chunk. Per-sentence checks do not replace it.
- **After a flagged chunk, release nothing more**, and replace the whole passage with the fallback in the terminal payload.
- **Don't stream any text that a later stage may rewrite.** Any new post-Narrator rewrite step (Dramaturge or similar) must set `stream_live=False` for its path.
- **The terminal `done` payload must stay identical to the `POST .../actions` response.** Clients treat it as authoritative and replace the streamed preview with it.
- **Don't cancel a turn when the client disconnects.** The turn task must finish and persist inside the shielded cleanup.
- **Only performers whose plain-text `_send` output reaches the player may set `streams_text = True`.** JSON and tool-calling performers must not stream.
- **Emits must do nothing when no sink is bound**, so benchmark and blocking-route behavior stays byte-identical.

## Verification / tests

- `tests/test_turn_stream.py` covers:
  - emits doing nothing without a sink, plus the bound and muted sink behavior
  - `SentenceGate` passthrough when there is no moderator
  - release of only checked sentences
  - blocking after a flagged sentence
  - `moderate_narration` falling back on a streamed hit
  - `process_action` streaming through the gate
- `tests/test_narrator_streaming.py` covers:
  - the Narrator streaming into a bound sink
  - `stream_live=False` muting it (the Dramaturge path)
  - no streaming without a sink
  - the `BaseLLMClient.stream_message` single-chunk default
- `tests/test_llm_streaming.py` covers the native OpenAI and Anthropic `stream_message` assembling the same `LLMResponse`.
- `tests/test_web_action_stream.py` covers:
  - the SSE happy path ending in `done`
  - service errors mapped to the same status and detail as the blocking route
  - unexpected errors becoming a generic 500 that does not leak exception text
  - `test_stream_close_waits_for_turn`, which shows that closing the stream early still lets the turn finish
- `tests/test_safety_engine_integration.py` (ADR-0006) keeps covering the non-streamed outbound fallback.

## Related files

- `llm/turn_stream.py`, `llm/base_client.py`, `llm/openai_client.py`, `llm/anthropic_client.py`
- `cast/base_performer_class.py`, `cast/narrator.py`, `cast/director.py`, `cast/director_execution.py`
- `engine/moderation.py`, `engine/game_engine.py`
- `interfaces/web/routes_stream.py`, `interfaces/web/action_stream.py`, `interfaces/web/routes.py`
- `interfaces/web/static/app.js`, `interfaces/web/static/style.css`
- `tests/test_turn_stream.py`, `tests/test_narrator_streaming.py`, `tests/test_llm_streaming.py`, `tests/test_web_action_stream.py`, `tests/_turn_stream_helpers.py`
