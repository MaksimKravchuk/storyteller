# ADR-0006: Content-safety moderation pipeline (web/engine surface)

Date: 2026-05-30
Status: Accepted
Decision owner: Max
Related: `safety/`, `engine/moderation.py`, `interfaces/web/auth_routes.py`, `db/repo_accounts.py`, `engine/game_engine.py`, `engine/factory.py`, `interfaces/web/routes.py`, `config.py`, KER-49, [ADR-0004](0004-retire-telegram-and-cli-player-clients.md)

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

**Amendment (2026-10-25):** when a turn stream is bound, outbound moderation also runs sentence by sentence before each streamed chunk is released, and the full-passage check still runs afterwards. See [ADR-0022](0022-stream-narrator-prose-over-sse.md).

**Amendment (2026-10-25, decided by Max): plain OpenAI `violence` is no longer scored.** `OpenAIModerationProvider` maps only `violence/graphic` to `ModerationCategory.VIOLENCE`; the plain `violence` score is ignored. `omni-moderation-latest` scores ordinary scuffles and attacks at >= 0.8 (HIGH), so `violence=HIGH` alone did not keep sword fights narrating. Production evidence: the narration "Он хватает тебя за плащ, валит на землю…" scored `violence=0.855`, `violence/graphic=0.006` and was suppressed; the player action "Бью стражника мечом" scored `violence=0.943` on input and was refused with HTTP 400. Gore (`violence/graphic`) is still gated at the `violence` threshold.

**Amendment (2026-10-25, decided by Max): account-level 18+ switch.** Each account carries `accounts.mature_content` (boolean, default false; Alembic `b7c8d9e0f1a2`). The player toggles it in the web UI Account dialog, which calls `PUT /api/me/preferences` (`GET /api/me` reports the current value). When on, `VIOLENCE` and `SEXUAL` are exempt from moderation for that player's turns, inbound and outbound: `ModerationThresholds.exempt` holds those categories and `is_violation` never fires for them. `SEXUAL_MINORS`, `SELF_HARM`, `HATE`, `HARASSMENT`, `ILLICIT` and `PROMPT_INJECTION` stay gated at their normal thresholds whatever the switch says. Mechanism: the web service builds a per-player `Config` copy with `safety_mature_content=True` (`player_cfg`) before `begin_session` / `resume_session`, so the moderator is still built by `safety.factory` and the gate stays at the engine seam. The switch takes effect from the player's next turn. Setting `SAFETY_MATURE_CONTENT=true` in the environment applies the same exemption server-wide.

## Rationale

- Guarding at the engine seam means every current and future engine-driven surface inherits both inbound and outbound moderation for free — there is no per-client moderation to forget to wire. This is the consumer-seam lesson from prior regressions applied to safety.
- The heuristic provider is independent of the paid moderation API, so prompt-injection defense works with no key configured and survives an OpenAI outage.
- HIGH-by-default violence keeps historically faithful narration (sieges, duels) from tripping the gate, while minors/self-harm/injection stay strict.
- Replacing flagged narration with a fallback (rather than erroring) keeps the turn alive — the player is never shown a stack trace for an outbound flag.
- Dropping plain `violence` (2026-10-25): an attack is the normal material of an adventure story. Gating it refused ordinary player moves and blanked ordinary narration. Gore is the part worth gating by default.
- The 18+ switch (2026-10-25): adults who want graphic violence or sexual content can opt in per account without loosening the server defaults for everyone else. The categories that protect minors, vulnerable players, other people, and the engine itself (sexual_minors, self_harm, hate, harassment, illicit, prompt_injection) are not up to the player.

## Alternatives considered

### Moderate only in the web route
Reject player input at the HTTP boundary and skip outbound checks. Rejected: it leaves Narrator output unmoderated and re-introduces the per-client wiring tax that ADR-0004 just removed.

### Custom/LLM-judge classifier
A bespoke classifier or an LLM-as-judge moderation call. Rejected for KER-49 scope: higher latency/cost and more tuning surface than the heuristic + omni-moderation combination; can be added as another provider later.

### Keep plain `violence` and raise its threshold (2026-10-25)
Rejected: the `violence` threshold is already HIGH, the top of the scale, and ordinary attacks score in the HIGH bucket. No threshold separates a sword blow from gore on the plain score; `violence/graphic` does.

### Global mature-content toggle only (2026-10-25)
A server-wide env flag. Kept as an operator override (`SAFETY_MATURE_CONTENT`) but not the main mechanism: the opt-in is a per-player choice, and one server serves many players.

### Let the 18+ switch exempt every category (2026-10-25)
Rejected: sexual content involving minors, self-harm encouragement, hate, harassment, illicit instructions, and prompt injection are not matters of player taste.

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
- With plain `violence` unscored, non-graphic violent content passes for every player, 18+ or not. Only `violence/graphic` still trips the violence gate.
- Opted-in players can receive graphic violence and sexual content. There is no age verification behind the switch; it is a self-declared preference.
- A future non-web client must still translate `SafetyRejectedError` to its own refusal affordance.

What future agents must preserve:
- Keep the moderation gate at the engine seam (`process_action`); do not move it into a single client.
- Never log or return source prose for a flagged event — category + severity only.
- New player surfaces inherit moderation by going through the engine; do not bypass it.
- If a provider is added, preserve the fail-safe aggregation (a provider error must not mask another provider's flag).
- Do not re-map plain OpenAI `violence` to `VIOLENCE` without Max's approval; only `violence/graphic` feeds that category.
- The 18+ exemption covers `VIOLENCE` and `SEXUAL` only. Never add `SEXUAL_MINORS`, `SELF_HARM`, `HATE`, `HARASSMENT`, `ILLICIT` or `PROMPT_INJECTION` to it.
- Apply the switch by building a per-player `Config` for the engine (`player_cfg`), not by skipping moderation in the route; the gate stays at the engine seam.
- The switch defaults to off. New accounts and unauthenticated players get the full defaults.

## Verification / tests

- `tests/test_safety_moderator.py` — provider aggregation, threshold rules, prompt-injection heuristics, refusal messaging, log/exception sanitisation.
- `tests/test_safety_engine_integration.py` — inbound rejection and outbound fallback through `GameEngine`; `violence=HIGH` regression-locks medium-violence pass-through.
- `tests/test_safety_web_api.py` — flagged input returns HTTP 400 at the route seam.
- `tests/test_safety_factory.py` — provider selection from config (heuristic always; OpenAI only when keyed); `test_build_moderator_mature_content_exemptions` / `test_build_moderator_default_has_no_exemptions` lock the exempt set to exactly `VIOLENCE` + `SEXUAL`.
- `tests/test_safety_moderator.py::test_severities_from_response_ignores_plain_violence` — plain `violence` scores are dropped; `test_exempt_category_is_never_a_violation` covers the exemption rule.
- `tests/test_safety_recorded_scores.py` — default moderation decisions on scores recorded from the live `omni-moderation-latest` endpoint (`tests/fixtures/moderation_scores.json`): ordinary EN/RU fights, threats, theft, arson and fight narration pass; gore and self-harm block. Hand-picked scores elsewhere never matched the real distribution (a sword blow scores `violence` ≈ 0.9, not MEDIUM). Re-record with `tests/fixtures/record_moderation_scores.py` when the moderation model changes.
- `tests/test_web_mature_content.py` — `/api/me` reports the switch, `PUT /api/me/preferences` stores it (auth required), and start/turn engines get the player's mature config.
- `tests/db/test_repo_accounts_mature.py` — `accounts.mature_content` DB round-trip.

## Related files

- `safety/` (`moderator.py`, `heuristic.py`, `openai_provider.py`, `factory.py`, `result.py`, `thresholds.py`)
- `engine/moderation.py`, `engine/game_engine.py`, `engine/factory.py`
- `interfaces/web/routes.py`, `interfaces/web/action_errors.py`
- `interfaces/web/auth_routes.py`, `interfaces/web/service.py`, `interfaces/web/service_helpers.py`, `interfaces/web/beta_auth.py`, `interfaces/web/static/` (Account dialog)
- `db/tables.py`, `db/repo_accounts.py`, `alembic/versions/b7c8d9e0f1a2_add_mature_content_to_accounts.py`
- `config.py`
- `docs/studio/09-founder-decision-register.md`
