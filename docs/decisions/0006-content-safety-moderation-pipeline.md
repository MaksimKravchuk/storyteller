# ADR-0006: Content-safety moderation pipeline (web/engine surface)

Date: 2026-05-30
Status: Accepted
Decision owner: Max
Related: `safety/`, `engine/moderation.py`, `engine/game_engine.py`, `engine/factory.py`, `interfaces/web/routes.py`, `config.py`, KER-49, [ADR-0004](0004-retire-telegram-and-cli-player-clients.md)

## Context

Storyteller forwards raw player text to LLM-backed agents and returns LLM-authored narration to players. Neither direction was moderated: a player could attempt prompt injection or steer the narrative toward disallowed content, and the Narrator could surface unsafe prose. KER-49 asked for an inbound + outbound moderation pass.

The original implementation (PR #194) also wired a refusal path through the Telegram handler. Telegram and the CLI were retired in [ADR-0004](0004-retire-telegram-and-cli-player-clients.md) (#295), so that surface no longer exists; the moderator must serve the web/API surface and the engine only.

## Decision

Add a `safety/` package whose `Moderator` aggregates pluggable providers and applies per-category severity thresholds. It is wired into `GameEngine.process_action` via `engine/moderation.py`:

- **Inbound** — the player action is moderated *before* it reaches the Director. A threshold-crossing result raises `SafetyRejectedError`. The web route translates it to **HTTP 400** carrying a user-facing refusal message.
- **Outbound** — the Narrator's prose is moderated on the way out. A threshold-crossing result suppresses the original prose and returns a safe-fallback string instead; the source prose is never returned to the player.

Providers: an always-on `HeuristicProvider` for prompt-injection patterns (which the OpenAI moderation endpoint does not surface) plus an `OpenAIModerationProvider` against `omni-moderation-latest`, added only when an OpenAI key is configured. Provider calls fan out with `asyncio.gather(return_exceptions=True)` so a transient provider outage cannot silently drop a HIGH-severity heuristic hit.

Per-category thresholds are configurable via env vars (`SAFETY_THRESHOLD_VIOLENCE`, …). Defaults are tuned for historical text quests: `violence=HIGH` (so medium-severity sword fights narrate), `sexual_minors=LOW`, `self_harm=MEDIUM`, `prompt_injection=MEDIUM`. The whole pass is gated by `SAFETY_ENABLED` (default on). Flagged events log category + severity + length only — source prose never reaches log sinks; OpenAI exception bodies are sanitized so URLs/headers/payloads cannot leak into HTTP detail or logs.

The moderation gate lives at the **engine seam** (`process_action`), not in any single client. The web route only translates the resulting exception to HTTP.

## Rationale

- Guarding at the engine seam means every current and future engine-driven surface inherits both inbound and outbound moderation for free — there is no per-client moderation to forget to wire. This is the consumer-seam lesson from prior regressions applied to safety.
- The heuristic provider is independent of the paid moderation API, so prompt-injection defense works with no key configured and survives an OpenAI outage.
- HIGH-by-default violence keeps historically faithful narration (sieges, duels) from tripping the gate, while minors/self-harm/injection stay strict.
- Replacing flagged narration with a fallback (rather than erroring) keeps the turn alive — the player is never shown a stack trace for an outbound flag.

## Alternatives considered

### Moderate only in the web route
Reject player input at the HTTP boundary and skip outbound checks. Rejected: it leaves Narrator output unmoderated and re-introduces the per-client wiring tax that ADR-0004 just removed.

### Custom/LLM-judge classifier
A bespoke classifier or an LLM-as-judge moderation call. Rejected for KER-49 scope: higher latency/cost and more tuning surface than the heuristic + omni-moderation combination; can be added as another provider later.

### Moderate the `start_game` setting input
Run the premise text through inbound moderation too. Left out of scope per the issue — the inbound check fires at `process_action` time only.

## Consequences

Positive:
- One moderation gate covers all engine-driven play; new surfaces inherit it by calling `process_action`.
- Prompt-injection defense works without any API key.
- Operators can ratchet any category up or down without code changes.

Tradeoffs / risks:
- Every action and every narration pays a moderation round-trip (heuristic always; OpenAI when keyed).
- Threshold defaults are a product judgement and may need recalibration against real play.
- A future non-web client must still translate `SafetyRejectedError` to its own refusal affordance.

What future agents must preserve:
- Keep the moderation gate at the engine seam (`process_action`); do not move it into a single client.
- Never log or return source prose for a flagged event — category + severity only.
- New player surfaces inherit moderation by going through the engine; do not bypass it.
- If a provider is added, preserve the fail-safe aggregation (a provider error must not mask another provider's flag).

## Verification / tests

- `tests/test_safety_moderator.py` — provider aggregation, threshold rules, prompt-injection heuristics, refusal messaging, log/exception sanitisation.
- `tests/test_safety_engine_integration.py` — inbound rejection and outbound fallback through `GameEngine`; `violence=HIGH` regression-locks medium-violence pass-through.
- `tests/test_safety_web_api.py` — flagged input returns HTTP 400 at the route seam.
- `tests/test_safety_factory.py` — provider selection from config (heuristic always; OpenAI only when keyed).

## Related files

- `safety/` (`moderator.py`, `heuristic.py`, `openai_provider.py`, `factory.py`, `result.py`, `thresholds.py`)
- `engine/moderation.py`, `engine/game_engine.py`, `engine/factory.py`
- `interfaces/web/routes.py`, `interfaces/web/action_errors.py`
- `config.py`
- `docs/studio/09-founder-decision-register.md`
