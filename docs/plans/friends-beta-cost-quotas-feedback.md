# Friends Beta cost, quotas, feedback, and admin docs implementation plan

Status: Draft implementation plan  
Branch: `docs/friends-beta-v0-2-plan`  
Issues: #240, #241, #242, #243, #244, #245  
Do not commit from this planning task.

## Goal

Ship the Friends Beta operating layer that makes LLM spend attributable, bounded, and reviewable while giving testers friendly failure states and an in-app feedback path tied to their game context.

## Existing repo facts this plan relies on

- `db/tables.py` already defines `ai_call_logs` with `session_id`, `turn_number`, `model`, `prompt_tokens`, `completion_tokens`, and `created_at`.
- `db/repo_ai_logs.py` already writes and reads AI call logs through `AILogStore`.
- `interfaces/web/routes.py` exposes the current player API: `GET /api/games/current`, `POST /api/games`, `POST /api/games/{game_id}/actions`.
- `interfaces/web/service.py` is the right boundary for player-visible start/turn policy checks before invoking the engine.
- `interfaces/web/schemas.py`, `interfaces/web/static/index.html`, and `interfaces/web/static/app.js` own the browser contract and UI.
- `interfaces/admin.py` / `interfaces/admin_dashboard.html` are the existing admin surface.
- Current web identity is cookie-backed via `interfaces/web/deps.py:get_player_id`; later Supabase/auth work should replace or augment this with real user/account IDs.
- No Alembic migrations directory is present in this checkout; schema changes are currently represented in `db/tables.py` and any project-specific DB init path/tests must be updated with the same table definitions.

## Decisions and defaults

Use these beta defaults from `docs/studio/09-founder-decision-register.md` unless Max changes them:

- Initial global beta LLM budget: `$50`.
- Per-user daily quota: `20` turns.
- Per-user weekly quota: `50` turns.
- Max active games per user: `3`.
- Feedback payload includes user, game, turn, category, free text, timestamp, and app/runtime context where available.

Implementation should fail closed: when attribution, quota lookup, kill switch, or provider status cannot be evaluated safely, the player should see a friendly beta-paused/provider-unavailable message rather than consuming budget invisibly.

## Work package 1 — Cost telemetry foundation (#240)

Outcome: every AI call can be rolled up by user, session/game, day, and model with deterministic cost math.

### 1.1 Add user/game attribution columns

Paths:

- `db/tables.py`
- `db/repo_ai_logs.py`
- `db/repository.py`
- tests under `tests/`

Tasks:

1. Add nullable attribution columns to `ai_call_logs`:
   - `user_id` `Text` or `_UUID_STR` depending on the account model introduced by auth work.
   - `game_state_id` `_UUID_STR`, nullable FK to `game_states.id` if reliably available at log-save time; otherwise nullable text/UUID with a follow-up backfill path.
2. Add indexes:
   - `idx_ai_calls_user_created` on `user_id`, `created_at`.
   - `idx_ai_calls_model_created` on `model`, `created_at`.
   - `idx_ai_calls_game_state` on `game_state_id`.
3. Update `AILogStore.save()` to accept optional `user_id` and `game_state_id` parameters and include them on every inserted row.
4. Update the persistence boundary that calls `repo.ai_logs.save(...)` to pass the authenticated/cookie user and game/session context. Likely path: `engine/session_ops.py` or the helper used by `persist_engine_state(...)`; confirm the exact call site before editing.
5. Keep existing log writes backward compatible for tests and non-web interfaces by allowing `None` attribution.

Tests/verification:

- Unit test `AILogStore.save()` inserts `user_id` and `game_state_id` when provided.
- Regression test that old log payloads without token counts or attribution still insert.
- Run targeted tests: `uv run pytest tests/test_*ai* tests/test_web_api.py`.

### 1.2 Add model pricing config and cost calculator

Paths:

- `config.py`
- new `costs/model_pricing.py`
- new `costs/__init__.py`
- tests: new `tests/test_model_pricing.py`

Tasks:

1. Add a small pricing module with a checked-in default map for active models, expressed as USD per 1M input tokens and USD per 1M output tokens.
2. Include all currently configured default models from `config.py`:
   - `gpt-5.4-mini`
   - `gpt-5.4-nano`
   - any OpenRouter/DeepSeek/Anthropic model IDs used in deployment env should be overridable.
3. Add env override support through `Config`, for example `model_pricing_json: str | None = None`, so Max can update prices without code deploy if provider pricing changes.
4. Implement pure functions:
   - `price_for_model(model: str, cfg: Config) -> ModelPrice | None`
   - `calculate_call_cost_usd(model, prompt_tokens, completion_tokens, cfg) -> Decimal`
   - missing token counts or unknown models return `0` plus an `unpriced` flag in reports, not an exception.
5. Use `Decimal`, not binary floats, for report math.

Tests/verification:

- Known prompt/completion token counts produce exact expected USD strings.
- Unknown model is reported as unpriced and does not crash.
- Env JSON override replaces a checked-in default.
- No API keys or prompts are included in report rows.

### 1.3 Add cost reporting repository methods

Paths:

- `db/repo_ai_logs.py`
- `db/repository.py`
- tests: `tests/test_ai_cost_reports.py`

Tasks:

1. Add `AILogStore.cost_rows(...)` or `AILogStore.usage_summary(...)` returning aggregated token usage grouped by:
   - user
   - session
   - game
   - UTC day
   - model
2. Include fields:
   - `prompt_tokens`
   - `completion_tokens`
   - `total_tokens`
   - `call_count`
   - `started_at`
   - `ended_at`
3. Keep price calculation in the pricing module/service layer so DB aggregation remains provider-agnostic.
4. Add optional date range filters for admin reports.

Tests/verification:

- Two models and two users aggregate independently.
- Null token counts are treated as zero but marked through report metadata if any unpriced/missing usage exists.
- Date filters include/exclude rows correctly.

### 1.4 Expose admin cost summary

Paths:

- `interfaces/admin.py`
- `interfaces/admin_dashboard.html`
- optional new `interfaces/admin_reports.py`
- tests: `tests/test_admin_cost_reports.py`

Tasks:

1. Add an admin JSON endpoint, for example `GET /api/admin/beta/cost-summary`, returning per-user and total summaries.
2. Add a simple admin dashboard section with:
   - total estimated spend
   - spend by user
   - spend by model
   - unpriced/missing-token warning count
   - link/button to export JSON/CSV if easy
3. Redact prompts/messages/responses from summary outputs.
4. Use UTC dates in response fields and label them explicitly.

Tests/verification:

- Admin endpoint returns computed costs for seeded AI logs.
- Response contains no `system_prompt`, `messages`, `response_content`, or secret-looking env values.
- Existing admin lifecycle tests still pass.

## Work package 2 — Plans, quotas, and global kill switch (#241, #244)

Outcome: beta gameplay is bounded before expensive engine work starts.

### 2.1 Add beta plan/entitlement model

Paths:

- `db/tables.py`
- new `db/repo_beta.py`
- `db/repository.py`
- tests: new `tests/test_beta_entitlements.py`

Tasks:

1. Add a user/account entitlement table if auth work has not already done so. Suggested table: `beta_users` with:
   - `id`
   - `user_id` unique, not null
   - `email` nullable until Supabase identity is merged
   - `plan` default `friend_beta`
   - `is_admin` default false
   - `created_at`, `updated_at`
2. Add a plan/quota table or checked-in config. Suggested table: `beta_plans` with:
   - `plan` primary key
   - `daily_turn_quota`
   - `weekly_turn_quota`
   - `max_active_games`
   - `enabled`
3. Seed/default plan values in repository fallback code if the table is empty:
   - `friend_beta`: 20/day, 50/week, 3 active games
   - `admin`: high or unlimited quotas, still subject to global kill switch unless explicitly bypassed by Max
4. Add repository methods:
   - `get_user_entitlement(user_id)`
   - `get_plan_limits(plan)`
   - `set_user_plan(user_id, plan)` for admin/manual operations

Tests/verification:

- Unknown user defaults to no entitlement or invite-required once auth gate is live.
- `friend_beta` returns expected defaults.
- `admin` plan behavior is explicit and tested.

### 2.2 Add global kill switch/runtime setting

Paths:

- `config.py`
- `db/tables.py` or existing `admin_settings`
- `db/repo_settings.py` or new `db/repo_beta.py`
- `interfaces/admin.py`
- tests: `tests/test_beta_kill_switch.py`

Tasks:

1. Add env-level switch to `Config`, for example:
   - `beta_enabled: bool = True`
   - `beta_kill_message: str = "Storyteller beta is paused while we tune the experience. Please try again later."`
2. Add optional DB/admin override using `admin_settings` or a new `beta_runtime_settings` table:
   - `beta_enabled`
   - `global_budget_usd`
   - `updated_at`
   - `updated_by`
3. Add admin read/update endpoint for the switch if it can be protected with the existing admin surface; otherwise document manual env/DB update for the first beta.
4. Ensure web start/action paths check kill switch before starting/resuming engine work.

Tests/verification:

- Env `BETA_ENABLED=false` blocks `POST /api/games` and `POST /api/games/{game_id}/actions`.
- Blocked response is 403 or 503 with friendly copy; choose one status and use it consistently.
- The engine is not invoked when beta is disabled.

### 2.3 Enforce daily/weekly turn quotas

Paths:

- new `beta/quotas.py`
- new `beta/__init__.py`
- `interfaces/web/service.py`
- `interfaces/web/routes.py`
- `interfaces/web/errors.py`
- `db/repo_ai_logs.py` or new `db/repo_beta.py`
- tests: `tests/test_beta_quotas.py`, `tests/test_web_api.py`

Tasks:

1. Count billable turns from persisted game/session state, not client input. Prefer a `turn_events` or session/game turn counter if available; otherwise use successful `ai_call_logs` turn numbers with non-null `turn_number`.
2. Implement `QuotaService.check_turn_allowed(user_id, now)` returning:
   - allowed/blocked
   - daily used/limit
   - weekly used/limit
   - reset timestamps
   - friendly reason key
3. Call quota check in `service.process_turn_for_player(...)` before `resume_session(...)` or before `engine.process_action(...)`; avoid AI/provider calls when blocked.
4. Decide whether game start consumes quota. Recommended: game start is subject to kill switch and active-game quota, but daily/weekly turn quota is consumed only by successful player turns.
5. Use UTC day and ISO week windows for all quota calculations.
6. Add route exception handling for `QuotaExceededError` with response body useful for UI:
   - `detail`
   - `code: "quota_exceeded"`
   - `reset_at`
   - `limit`
   - `used`

Tests/verification:

- User under daily and weekly limit can take a turn.
- User at daily limit is blocked before engine invocation.
- User at weekly limit is blocked before engine invocation.
- Another user's usage does not count against this user.
- Boundary at UTC midnight/week reset is tested with fixed `now`.

### 2.4 Enforce max active games

Paths:

- `db/repo_sessions.py`
- `interfaces/web/service.py`
- `interfaces/web/routes.py`
- tests: `tests/test_beta_active_games.py`

Tasks:

1. Add repository method to count active sessions/games for a user:
   - `count_active_games(user_id)`
   - define active as sessions in `playing` state that are not archived/deleted once account-owned stories work lands.
2. Check count before `repo.sessions.create_web(...)` in `start_game_for_player(...)`.
3. Current web route says starting a new game replaces any existing one; account-owned stories will change this. Make the quota check compatible with both:
   - before account-owned stories: count latest/current active session only.
   - after account-owned stories: count all unarchived active games.
4. Add friendly response `code: "active_game_limit"` and copy suggesting the player continue or archive an existing story.

Tests/verification:

- User with fewer than 3 active games can start.
- User with 3 active games cannot start a 4th.
- Archived/deleted games do not count once those states exist.

### 2.5 Add global budget guard

Paths:

- `costs/model_pricing.py`
- `db/repo_ai_logs.py`
- `beta/quotas.py`
- tests: `tests/test_beta_budget_guard.py`

Tasks:

1. Use cost summary from AI logs to estimate global beta spend to date.
2. Add warning threshold and hard-stop threshold:
   - warn at 80% of configured budget
   - block at 100% of configured budget
3. Wire hard-stop into the same pre-engine policy check as kill switch and quotas.
4. Surface warning in admin cost summary; do not show budget internals to normal players beyond friendly beta-paused copy.

Tests/verification:

- Below budget allows turns.
- At/above hard budget blocks before engine invocation.
- Unknown/unpriced model spend is reported but does not silently lower known estimated spend; admin response flags uncertainty.

## Work package 3 — Friendly player-facing failures (#241)

Outcome: beta constraints and provider failures are understandable and non-technical.

Paths:

- `interfaces/web/errors.py`
- `interfaces/web/routes.py`
- `interfaces/web/schemas.py`
- `interfaces/web/static/app.js`
- `interfaces/web/static/index.html`
- tests: `tests/test_web_api.py`

Tasks:

1. Add typed web error codes for:
   - `beta_disabled`
   - `quota_exceeded`
   - `active_game_limit`
   - `global_budget_reached`
   - `provider_unavailable`
2. Standardize JSON error shape for player API errors:
   - `detail: string`
   - `code: string`
   - optional `reset_at`, `limit`, `used`
3. Update `routes.py` to translate service exceptions into the standard shape.
4. Update `app.js:parseError(...)` to prefer structured `detail` and optionally render quota reset hints.
5. Ensure all player-visible copy avoids stack traces, provider names, token counts, or cost details.

Tests/verification:

- API tests assert exact status code and `code` for each blocked state.
- UI parse helper behavior is covered if a JS test harness exists; otherwise add a manual QA checklist in the PR body.
- Provider auth failures continue to return the friendly provider-unavailable copy already present in `routes.py`.

Suggested copy:

- Beta paused: "Storyteller beta is paused while we tune the experience. Please try again later."
- Daily quota: "You have reached today’s beta turn limit. Your turns refresh tomorrow."
- Weekly quota: "You have reached this week’s beta turn limit. Your turns refresh next week."
- Active games: "You have reached the beta limit for active stories. Continue or archive an existing story before starting another."
- Provider unavailable: "Storyteller is temporarily unable to reach its story engine. Please try again later."

## Work package 4 — In-app feedback with game context (#242)

Outcome: testers can report confusion, bugs, delight, and suggestions without leaving the game.

### 4.1 Add feedback persistence

Paths:

- `db/tables.py`
- new `db/repo_feedback.py`
- `db/repository.py`
- tests: `tests/test_feedback_repo.py`

Tasks:

1. Add `beta_feedback` table:
   - `id` UUID primary key
   - `user_id` not null when auth exists; nullable during cookie bridge if needed
   - `email` nullable
   - `session_id` nullable FK to `sessions.id`
   - `game_state_id` nullable FK to `game_states.id`
   - `turn_number` nullable integer
   - `category` string, e.g. `bug`, `confusing`, `delight`, `suggestion`, `other`
   - `message` text, not null
   - `page_url` text nullable
   - `user_agent` text nullable
   - `created_at` timestamp
2. Add indexes:
   - `idx_feedback_user_created`
   - `idx_feedback_game_turn`
   - `idx_feedback_category_created`
3. Add repository methods:
   - `create_feedback(...)`
   - `list_feedback(...)` with date/category filters for admin/export
4. Do not store full prompts/responses in feedback rows; game/turn references are enough for later lookup by admins.

Tests/verification:

- Feedback row stores user/game/turn/category/message.
- Invalid category is rejected at schema/service layer.
- Feedback from one user cannot spoof another user's game context.

### 4.2 Add feedback API

Paths:

- `interfaces/web/schemas.py`
- `interfaces/web/routes.py`
- `interfaces/web/service.py`
- tests: `tests/test_web_feedback.py`

Tasks:

1. Add schemas:
   - `FeedbackRequest`
   - `FeedbackResponse`
2. Add route, suggested:
   - `POST /api/feedback`
3. Server derives `user_id` from auth/cookie dependency; client may send `game_id` and `turn_number`, but server validates ownership by loading the current/target session for that user.
4. Accept feedback even if no current game exists, but include game/turn context when available.
5. Return a simple success body with feedback id and thank-you message.

Tests/verification:

- Authenticated/cookie user can submit feedback for current game.
- Feedback for another user's game is rejected or stripped of game context.
- Empty/too-long feedback is rejected with 422.
- Feedback endpoint does not call the engine or provider.

### 4.3 Add feedback UI

Paths:

- `interfaces/web/static/index.html`
- `interfaces/web/static/app.js`
- web CSS file if present; otherwise inline existing stylesheet in `index.html`
- docs QA checklist

Tasks:

1. Add a persistent "Feedback" button visible during gameplay and optionally on the start screen.
2. Add modal/panel with:
   - category dropdown
   - free-text textarea
   - submit/cancel buttons
   - small note: "Feedback includes your current story and turn so Max can debug it."
3. Include current `game_id` and last known `turn_count` in the request.
4. Preserve the player's typed action if the feedback panel is opened mid-turn.
5. Show a thank-you state and handle errors without losing typed feedback.

Tests/verification:

- Manual browser check: submit feedback during a game and verify DB/admin row has user/game/turn.
- Manual browser check: failed submit leaves message text intact.
- Existing smoke doc `docs/qa/player-web-ui-smoke.md` gets a feedback step in a later PR.

### 4.4 Add admin feedback review/export

Paths:

- `interfaces/admin.py`
- `interfaces/admin_dashboard.html`
- optional `interfaces/admin_reports.py`
- tests: `tests/test_admin_feedback.py`

Tasks:

1. Add admin JSON endpoint, for example `GET /api/admin/beta/feedback`.
2. Add dashboard section/table showing newest feedback with user/email, category, game/session, turn, and created time.
3. Add CSV or JSON export endpoint if small enough for the first PR.
4. Keep full feedback message visible to admin, but do not expose prompts/responses inline.

Tests/verification:

- Admin endpoint returns newest first.
- Filters by category/date work if implemented.
- Export response has stable headers/fields.

## Work package 5 — Beta admin/onboarding docs (#243)

Outcome: Max can invite testers responsibly and testers know what to expect.

Paths:

- new `docs/beta/friends-beta-admin.md`
- new `docs/beta/friends-beta-tester-guide.md`
- update `docs/qa/player-web-ui-smoke.md`
- optional update `docs/studio/03-release-checklist.md`

Tasks:

1. Create `docs/beta/friends-beta-admin.md` with:
   - Wave 1 invite checklist
   - how to add/remove invited users once auth work lands
   - how to check cost summary
   - how to read feedback
   - how to toggle global kill switch
   - daily beta monitoring checklist
   - rollback/pause instructions linking to `docs/studio/08-fly-release-rollback.md`
2. Create `docs/beta/friends-beta-tester-guide.md` with:
   - invite copy
   - sign-in instructions
   - PWA install instructions for iOS Safari, Android Chrome, and desktop Chrome/Safari where supported
   - gameplay expectations
   - feedback instructions
   - known limitations
   - lightweight privacy/beta disclaimer
3. Update QA smoke doc with beta-specific checks:
   - sign in as invited user
   - start story
   - play a turn
   - hit feedback form
   - verify friendly quota/paused message via test config
4. Record Max-approved contact/privacy channel once available; until then mark it `TODO(Max approval)`.

Tests/verification:

- Docs have no secrets, private tester emails, or live invite links.
- Docs mention beta data stored: account identifiers, story prompts/actions, generated narration, feedback, AI provider calls.
- Instructions match actual UI labels after implementation PRs land.

## Work package 6 — Subscription readiness report (#245)

Outcome: telemetry supports a later pricing decision without building Stripe now.

Paths:

- new `docs/beta/subscription-pricing-hypothesis.md` after Wave 1 data exists
- admin cost summary endpoint from Work package 1
- optional new CLI/report script: `scripts/beta_cost_report.py`

Tasks:

1. Add report fields needed later:
   - cost per started game
   - cost per 20-turn session
   - median/mean turns per active user
   - retention proxy: users returning on another day
   - feedback count by category
2. After Wave 1, generate a pricing hypothesis doc with at least two tiers and quota assumptions.
3. Explicitly keep Stripe out of scope for v0.2.

Tests/verification:

- Report can be generated from local seeded data.
- Pricing doc labels assumptions and sample size clearly.

## Suggested PR order

1. **Telemetry schema + pricing calculator** (#240): attribution columns, pricing module, pure cost tests.
2. **Admin cost summary** (#240): aggregation repository and admin report endpoint/UI.
3. **Plans/quotas/kill switch service** (#241/#244): plan defaults, policy checks, typed service errors.
4. **Web quota enforcement + friendly messages** (#241): route/UI error handling and active-game limit.
5. **Feedback persistence/API/UI** (#242): feedback table, route, client panel.
6. **Admin feedback review/export** (#242): dashboard table/export.
7. **Beta admin/tester docs** (#243): invite/admin/privacy/known-limits docs and QA checklist.
8. **Post-Wave pricing hypothesis** (#245): only after real beta telemetry exists.

## Cross-cutting verification before beta gate

Run the narrow checks in each PR plus, before Gate 3:

```bash
uv run pytest tests/test_web_api.py tests/test_admin_lifecycle.py
uv run pytest tests/test_ai_cost_reports.py tests/test_beta_quotas.py tests/test_web_feedback.py
uv run pytest
```

Manual beta QA:

1. Start local web app with beta enabled.
2. Sign in or use test user identity.
3. Start a story and confirm an AI log row has user/session/game attribution.
4. Play a successful turn and confirm quota usage increments.
5. Force daily quota exceeded and confirm no engine/provider call occurs.
6. Set kill switch off and confirm start/action are blocked with friendly copy.
7. Submit feedback during a game and confirm admin can see user/game/turn/category/message.
8. Open admin cost summary and confirm total cost, per-user rows, per-model rows, and unpriced warnings.
9. Confirm docs contain no secrets or private tester data.

## Open implementation questions

- Final user ID type depends on the auth/account-owned story implementation. If Supabase IDs are text UUID strings, store them consistently as `Text` or native UUID after confirming format.
- If multiple web games become available before quota work lands, active-game counting must use the account-owned story state model rather than current `get_latest_web` behavior.
- Admin endpoint protection should be confirmed before exposing cost/feedback reports on any deployed environment.
- Model prices must be checked against provider pricing at implementation time; keep the default table small and overrideable.
