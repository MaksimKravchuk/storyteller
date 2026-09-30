# ADR-0020: Story library posters — deterministic playbills, illustrations on request

Date: 2026-09-30
Status: Proposed
Decision owner: Max. He chose the hybrid variant in session on 2026-09-30: every story gets a playbill generated after the prologue, and a painted illustration is made only when the player asks ("just do it"). Turning paid illustrations on for a deployed beta is a separate operator action; see Consequences.
Decision type: Product (player-facing library UX, an optional paid feature) + Architecture (a new image-model client, new web routes) + Persistence (a new `story_posters` table) + Operations (spend, quota, moderation)
Extends: `docs/decisions/0019-player-ui-stage-visual-language.md` (the "stage" visual language, `PLACE_ICONS` / `DAYPART_ICONS`, name-gated cast chips)
Related: founder-register D004 (cost budget), D006 (PWA online-required), D007 (privacy posture) and D010 (release approval / material spend) in `docs/studio/09-founder-decision-register.md`; `docs/decisions/0006-content-safety-moderation-pipeline.md`; `interfaces/web/{playbill.py,library_rows.py,poster_art.py,poster_errors.py,service_poster.py,routes_poster.py,schemas_library.py,service.py,auth_routes.py}`, `interfaces/web/static/{app.js,style.css}`, `llm/image_client.py`, `db/{tables.py,repo_posters.py,repo_web_games.py,repo_ai_logs.py}`, `alembic/versions/a9b0c1d2e3f4_add_story_posters.py`, `config.py`, `costs/model_pricing.py`, `.env.example`

## Context

ADR-0019 gave the play screen an identity, but the "My Stories" library still listed each story as a title, a setting and a turn count. Two stories set in the same city looked identical, and nothing on the list recalled how a story began or who was in it.

A poster per story fixes that. A poster can come from two very different sources:

- **A deterministic projection of game state.** Everything a playbill needs already exists after the prologue: the opening narration, the setting, the player character, the current location and its type, the time of day, and the name-gated people in the scene (`build_world_view`). This is free, instant and language-neutral where it reuses ADR-0019's icons.
- **An image model.** A painted poster is far more memorable, but each image is a paid call. Its prompt carries player-authored text (the character's appearance) to a third party, and it needs content moderation like any other model input.

Constraints carried from earlier decisions:

- **D004 / D010.** A $50 global beta budget, fail-closed quota UX, and "materially increase spend" needs Max's approval. Any new paid call type must be priced, logged and budget-gated.
- **D007.** Testers are told that AI requests go to model providers. An image prompt that includes the player's described appearance is such a request.
- **ADR-0006 (content safety, `0006-content-safety-moderation-pipeline.md`).** Model inputs derived from player text are moderated, and flagged content is never logged or returned.
- **ADR-0019.** NPC names reach the player only through `NPCCard.label_for_player` (`ScenePerson.label`). Location types and dayparts are drawn with `PLACE_ICONS` / `DAYPART_ICONS`, not printed as slugs. `PRECACHE_URLS` stays unchanged (D006).

Three variants were put to Max: typographic playbills only, a painted poster for every story, or a hybrid. He chose the **hybrid**.

## Decision

### 1. Every new web story gets a deterministic playbill, captured once after the prologue

`interfaces/web/playbill.py` `build_playbill(game_state)` projects the post-prologue `GameState` into a `Playbill` (`interfaces/web/schemas_library.py`). No LLM is called.

| Field | Source |
| --- | --- |
| `tagline` | The first sentence of the opening narration (the first `conversation_log` response). A sentence ends at `.`, `!`, `?` or `…` followed by a space, or at the Japanese full-width `。`, `！` or `？`. Markdown is stripped, whitespace collapsed, and the result is clipped at a word boundary to 160 chars with `…`. |
| `setting`, `era`, `region` | `Setting.name`, `Setting.time_period`, `Setting.region` |
| `hero`, `hero_look` | `player.name`, `player.appearance` |
| `place`, `place_type` | `WorldView.map.current` name and `location_type` (`None` / `"generic"` with no current location) |
| `daypart` | `WorldView.clock.time_of_day` |
| `cast` | The first 4 `WorldView.people` as `{label, known}`: the `ScenePerson.label` → `NPCCard.label_for_player` path, the same one the stage header uses |

`start_game_for_player` calls `save_playbill` after the engine start succeeds and before `_mark_session_playing` commits, so the playbill lands in the same transaction as the new session. The projection is pure and reuses the same `build_world_view` the start snapshot already runs, so it is not wrapped in its own error handling: a failure there is a code bug that would break the snapshot too. The playbill is a snapshot of opening night. It is not refreshed as the story moves on.

### 2. Posters are stored in a new `story_posters` table

Alembic revision `a9b0c1d2e3f4` (revises `e8f9a0b1c2d3`) creates one row per session:

| Column | Type | Notes |
| --- | --- | --- |
| `session_id` | UUID, PK | FK `sessions.id` `ON DELETE CASCADE` |
| `playbill` | JSONB, not null | `Playbill.model_dump()` |
| `image` | BYTEA, nullable | The painted illustration, if any |
| `image_mime` | varchar(32), nullable | `image/webp` today |
| `image_created_at` | timestamptz, nullable | Set with `clock_timestamp()` on save; the daily quota counts it |
| `created_at` | timestamptz, not null | `now()` |

`db/repo_posters.py` `PosterStore` is reached as `repo.web_games.posters`, which keeps `GameRepository` the single persistence access point. `save_playbill` upserts the playbill and leaves any image alone. `save_image` updates the existing row. `get_playbill` returns `(playbill, has_image)` without reading the image bytes.

### 3. The library contract gains an optional playbill

`GET /api/games` outer-joins `story_posters`. Each `GameSummary` gains `playbill: Playbill | None` and `has_poster_image: bool`, where `has_poster_image` is computed in SQL as `image IS NOT NULL`, so listing never loads image bytes. `interfaces/web/library_rows.py` validates the stored JSON. An unreadable playbill logs a warning and falls back to the plain card.

**Legacy stories have no playbill and are not backfilled.** They keep the plain card and cannot be painted: `POST` returns 404.

### 4. The client draws the playbill and shows a painted image when one exists

In `app.js` / `style.css`, a card with a playbill gets a 2:3 poster frame:

- stage curtains (inline SVG), `PLACE_ICONS[place_type]` (falling back to `generic`) and `DAYPART_ICONS[daypart]`, tinted per daypart;
- the tagline;
- a billing line, "Starring *hero* · with *cast*". Known cast renders in the `--person` hue and strangers in italics, echoing the stage chips. The server sends `hero: null` when the player kept the engine's default name (`PlayerState.name`), so the client never hard-codes that default.

When `has_poster_image` is true, the client fetches `GET /api/games/{id}/poster` through `apiFetch` (so the auth header is sent), shows it as a blob object URL over the drawn art, and revokes the URLs whenever the library re-renders. A **Paint poster** button appears only when `GET /api/config/public` reports `poster_images_enabled` and the card has a playbill but no image. Errors appear on the card they belong to.

### 5. A painted illustration is made only on explicit player request, once per story

`POST /api/games/{game_id}/poster` (`routes_poster.py`) calls `service_poster.illustrate_poster`, which returns `201 {"has_poster_image": true}`. Every check that can refuse runs **before** the paid call. Checks from `BetaPolicy.ensure_open` onward run inside a poster-only lock, `quota_locks.player_lock("poster:" + player_id)`, so a 20–60 s painting never holds up the same player's turns or game starts:

1. `posters_available(cfg)`: `POSTER_IMAGES_ENABLED` is true **and** an OpenAI key is configured.
2. `BetaPolicy.ensure_open()`: the beta kill switch and the global budget (D004).
3. `owned_session_context`: the caller owns the story.
4. A playbill exists and has no image yet (one image per story).
5. The rolling 24-hour quota: `PosterStore.painted_since` counts this player's `story_posters` rows whose `image_created_at` falls in the window (joined through `sessions.web_player_id`). The call is refused at `POSTER_DAILY_IMAGE_QUOTA`.
6. Moderation: the prompt goes through `safety.factory.build_moderator(cfg)` as `ModerationDirection.INPUT`, the same moderator and thresholds as the ADR-0006 content-safety pipeline. The check is skipped when `SAFETY_ENABLED=false`. A flag refuses with the moderator's refusal message.
7. Paint, then commit the cost row before storing the image. The call is paid for once it returns, so its cost reaches the budget even if the store is refused or fails. Then store the image and commit.

The library disables a story's Archive button while its poster is being painted. Archiving mid-paint would otherwise hide the paid image along with the story. An image that lands on a story archived from another tab is still stored, and it counts toward the player's quota like any other painting.

`GET /api/games/{game_id}/poster` serves the bytes with the stored MIME type and `Cache-Control: private, max-age=31536000, immutable` (an illustration is written once and never replaced). It is owner-scoped in one joined query, `PosterStore.get_image_for_player(player_id, game_id)`, so another player's story, an archived story and a story without an image all return the same 404.

| Refusal | HTTP |
| --- | --- |
| Not owned, no playbill, or illustrations unavailable | 404 `No poster for this story` |
| Already painted | 409 |
| Daily poster quota reached | 429 |
| Moderation flagged | 400 with the moderator's refusal message (`engine.moderation.moderate_input` → `SafetyRejectedError`, mapped by `action_errors` exactly like a flagged player action) |
| Kill switch or global budget (`BetaAccessDeniedError`) | 503 with the beta message |
| Image provider failure (`PosterFailedError`) | 503 |

### 6. Images come from OpenAI `gpt-image-1-mini` through a dedicated client

`llm/image_client.py` defines an `ImageClient` protocol and `OpenAIImageClient`. The client requests `images.generate` at `1024x1536` (portrait), `output_format="webp"`, `output_compression=82`, the configured quality and `n=1`. It returns the bytes plus `usage.input_tokens` / `usage.output_tokens` and the duration. The OpenAI SDK is imported lazily, like `llm.openai_client`. Any provider exception becomes `PosterFailedError`.

This client sits apart from the chat LLM factory. It is not auto-detected from a model name and is not a `BasePerformer`.

### 7. The prompt paints the hero and the place, never the cast

`poster_art.poster_prompt(playbill)` asks for an illustrated vintage theatre poster built from `setting`, `era`, `region`, `place` (or `region`), `daypart`, `hero_look` (or "a lone traveller") and the tagline as mood. It forbids text, letters, captions and logos. **Cast names and the hero's name are not sent.** The client draws all typography.

### 8. Configuration and cost

| Env var | Default | Meaning |
| --- | --- | --- |
| `POSTER_IMAGES_ENABLED` | `false` | Operator switch for painted illustrations |
| `POSTER_IMAGE_MODEL` | `gpt-image-1-mini` | OpenAI image model |
| `POSTER_IMAGE_QUALITY` | `medium` | Passed through to `images.generate` |
| `POSTER_DAILY_IMAGE_QUOTA` | `3` (`ge=0`) | Paintings per player per rolling 24 h; `0` stops painting |

Each painting writes one `ai_call_logs` row with the following fields:

- `agent_name="PosterIllustrator"`
- the image `model`
- the prompt in `messages`
- a placeholder `response_content` (`"[image/webp, N bytes]"`)
- `prompt_tokens` / `completion_tokens` from the image usage
- `duration_ms`
- the player's `user_id`

`costs/model_pricing.py` gains a default price for `gpt-image-1-mini` of **$2.00 input / $8.00 output per million tokens**. This was taken from public price listings, not from an OpenAI invoice. `MODEL_PRICING_JSON` overrides it. The rows therefore count toward the global budget in `BetaPolicy`. They carry no `turn_number`, so they do **not** count toward D004's turn quotas.

### 9. Images live in Postgres `bytea`

There is one WebP per story, capped per player per day. At friends-beta scale the images stay in the database: no object store, no new credentials, no new origin.

## Rationale

Max chose the variant. The reasoning below is the agent's engineering case for it.

- **Every story gets an identity at zero marginal cost.** Everything on the playbill already exists after the prologue, so projecting it costs no model call, adds no latency and cannot fail a game start. Painting is the optional extra, not the baseline.
- **Paid work follows player intent, not game starts.** Painting only on request ties image spend to stories a player cares about. Painting at every start would spend on stories abandoned after one turn and would add seconds, or a background job, to the start path. The flag defaulting to `false`, one image per story, the per-player daily cap, `BetaPolicy.ensure_open` and cost rows in `ai_call_logs` keep this new spend class inside D004's budget model and D010's "materially increase spend" gate.
- **The cheap checks run before the expensive call.** Availability, budget, ownership, one-per-story, quota and moderation all run before `images.generate`, under a per-player poster lock. A refused request costs nothing, except for the OpenAI moderation call when a key is configured.
- **Name-gating stays single-path.** Cast labels come from `build_world_view`, the same `NPCCard.label_for_player` path as the stage header (ADR-0019, and §5 of `0006-player-dashboard-gui.md`). Leaving names out of the image prompt means the picture cannot leak a name the player has not learned, and text rendered by an image model, which is often garbled, never reaches the poster.
- **The poster speaks ADR-0019's language.** The drawn art reuses `PLACE_ICONS` / `DAYPART_ICONS` keyed by backend slugs, so it reads the same in Russian and English sessions. The tagline is prose the Narrator already wrote in the story's language and the player already read.
- **A stored snapshot keeps the library query cheap and the poster stable.** Computing the playbill while listing would mean deserialising every story's game state on each `GET /api/games`, and the poster would drift as the story moved on. A JSONB row plus a SQL `IS NOT NULL` flag keeps listing to one outer join.
- **`bytea` is the least moving parts for the beta.** Deleting a session cascades to its poster, which serves D007 deletion requests. Backups already cover the database, and no storage credentials, signed URLs or third-party origin are added. The owner-scoped `GET` needs no separate ACL layer.
- **The image client is kept separate from the chat layer.** Image generation is not a chat completion, is not part of turn flow and has no system prompt, so forcing it through `BasePerformer` or the model-name factory would blur both. The `ImageClient` protocol keeps the provider swappable and lets tests inject a fake.
- **Reusing the OpenAI key adds no new provider relationship.** OpenAI already receives gameplay requests (the default models are `gpt-5.4-*`) and moderation requests, so D007's "AI requests are sent to model providers" disclosure already names this recipient.

## Alternatives considered

### Alternative 1: Typographic playbill only

This has no spend, no privacy surface and no moderation path. It was **not chosen**: Max chose the hybrid. The typographic playbill ships as the default for every story, so this alternative is effectively what a deployment gets with `POSTER_IMAGES_ENABLED=false`.

### Alternative 2: Paint a poster for every story at start

This gives the most striking library. It was rejected because spend would scale with game starts rather than player interest, and the start path would gain latency or a background job. It would also send the player's appearance to the image model without the player asking, and a moderation refusal or provider error would then need handling during the prologue.

### Alternative 3: Have an LLM write the playbill copy (tagline, billing)

This would give punchier copy. It was rejected because it costs a model call per start and is non-deterministic. It would also open a second path by which NPC names could reach the player, outside `label_for_player`. The Narrator's own first sentence is already in the story's language and already seen by the player.

### Alternative 4: Compute the playbill when the library is listed

This needs no new table and is always current. It was rejected because the library query would have to load and deserialise full game state for every row. The poster would also change under the player, whereas opening night is what a playbill commemorates.

### Alternative 5: Object storage (S3 / Supabase Storage) for images

This is the standard answer at scale. It was **deferred**: it adds a service, credentials, lifecycle and deletion wiring, and possibly a new origin for D007, all for at most a few images per player per day. Revisit if `story_posters` grows enough to affect backup or restore time.

### Alternative 6: Route image calls through the `llm/` factory / a cast performer

This would give one model-client layer. It was rejected because image generation shares neither the chat interface, the system-prompt pattern nor turn orchestration. A poster is a library feature, not a performer on stage.

### Alternative 7: A calendar (UTC midnight) daily quota

This is simple to explain. It was rejected in favour of a rolling 24-hour window, which matches how `BetaPolicy` already counts D004 turn quotas (`_period_start` is `now - 1 day`) and avoids a burst on either side of midnight.

### Alternative 8: Backfill playbills for existing stories

This would give a uniform library. It was **not done**: it needs a one-off job over stored game states, and those stories are past their prologue, so the "opening night" snapshot would be wrong. Legacy stories keep the plain card.

## Consequences

Positive consequences:
- Every new story has a distinct, language-neutral poster in "My Stories" without any model call.
- Players who want a painted poster can have one, with spend bounded per story, per player per day and by the global budget.
- Poster spend shows up in the existing admin cost reports as its own agent (`PosterIllustrator`).
- `PRECACHE_URLS` and the service worker are unchanged (D006). The poster art is inline SVG in the precached `app.js`.

Tradeoffs / risks:
- **The default price is unverified.** $2 / $8 per M tokens comes from public listings. **Estimate (inferred, unverified):** a medium 1024×1536 image is on the order of 1.5k output tokens, about $0.01–0.02 per poster, so the default cap of 3 per player per day is a few cents per player per day. Check the first real `PosterIllustrator` rows in `ai_call_logs` against the OpenAI dashboard and correct `DEFAULT_MODEL_PRICES` or set `MODEL_PRICING_JSON`.
- **Unpriced models are invisible to the budget.** `calculate_call_cost_usd` treats a model without a price as $0. Pointing `POSTER_IMAGE_MODEL` at a model not in the price table without a `MODEL_PRICING_JSON` entry lets posters spend outside the D004 budget check.
- **The prompt carries player-authored text to OpenAI** (the character's appearance, and the tagline, which may contain a name the narration used). This is covered by the existing D007 / onboarding wording that AI requests go to model providers. The prompt is also retained in `ai_call_logs.messages`, like every other logged model input.
- **Moderation depends on configuration.** With `SAFETY_ENABLED=false` the prompt is not moderated. With no OpenAI key there is nothing to paint (`posters_available` is false), so the heuristic-only case does not arise.
- **"One per story" never overwrites, but a race can still pay twice.** `save_image` is a conditional `UPDATE … WHERE image IS NULL`, so the first stored image wins and a later one is refused (`PosterExistsError`). The losing call's cost row is already committed by then. The pre-call check runs under a per-process lock, so two workers could both pay for the same story before one of them loses the write. This is the same single-process limitation the turn quotas already accept.
- **Database growth.** Each WebP (roughly a few hundred KB at 1024×1536, q82; estimate) lives in Postgres and in its backups.
- **The playbill is frozen at the prologue.** The cast is whoever was on stage at the start, usually strangers, and the place and daypart are those of the opening scene.
- **English chrome remains**, as under ADR-0019: "Starring", "with", "Paint poster" and the refusal messages.
- **Enabling paid illustrations on a deployed beta is a Max action.** The flag defaults to `false`. Flipping it, or raising `POSTER_DAILY_IMAGE_QUOTA`, changes spend and falls under D010.

What future agents must preserve:
- **The playbill stays deterministic and free.** Do not add an LLM call to `build_playbill`. A playbill build failure must never fail or delay a game start.
- **Cast names come only from `build_world_view` / `ScenePerson.label`** (`NPCCard.label_for_player`). Do not read `NPCCard.name` or any other name field into the playbill or the library card.
- **The illustration prompt excludes names.** Do not add cast names or the hero's name to `poster_prompt`, and keep the "no text" instruction. Typography is drawn by the client.
- **Paid illustration only on an explicit player request.** Do not paint automatically at start, on list or in the background without a new decision.
- **All refusal checks run before the paid call, under the player lock:** availability, `BetaPolicy.ensure_open`, ownership, one-per-story, the rolling quota, then moderation. Do not reorder moderation or quota after `paint`.
- **Every painting writes an `ai_call_logs` row** with `agent_name="PosterIllustrator"`, the model, token usage and `user_id`. The global budget prices these rows; the daily quota counts `story_posters.image_created_at` instead, so renaming the log agent cannot change it. Any new image model must be priced (default table or `MODEL_PRICING_JSON`).
- **Poster rows must not carry `turn_number`**, so they stay out of D004's turn quotas.
- **Image reads are owner-scoped** and return 404 for both absent and foreign stories. Do not serve poster bytes from a public or unauthenticated URL.
- **The library query never loads image bytes.** Keep `has_poster_image` computed in SQL.
- **`POSTER_IMAGES_ENABLED` defaults to `false`.** Enabling it in a deployed beta, raising the quota or switching to a pricier model or quality is a D010 spend decision for Max.
- **Moving images out of Postgres** (object storage, CDN) is a new decision that touches D007 (origin, deletion) and should extend this ADR.

## Verification / tests

- **Playbill builder and start seam (automated).** `tests/test_web_playbill.py` covers:
  - tagline extraction, clipping and the empty opening;
  - projection of every field;
  - name-gated cast (`test_build_playbill_cast_is_name_gated`) and the 4-member cap;
  - no current location;
  - `save_playbill` writing the row and skipping unbuildable state;
  - `test_start_game_saves_playbill_before_commit` (the start-game consumer seam);
  - library rows carrying or tolerating a bad playbill.
- **Illustration service (automated).** `tests/test_web_poster.py` covers:
  - the prompt contains the hero's look and the place but not the cast (`test_prompt_uses_hero_and_place_not_cast`);
  - `posters_available` needs the flag and the key;
  - a successful paint stores, logs and commits;
  - the quota counts the `PosterIllustrator` agent;
  - each refusal: unavailable, not owned, missing or existing playbill, quota, moderation, provider failure;
  - owner-scoped image lookup.
- **Routes (automated).** `tests/test_web_poster_routes.py` covers 201 on paint, the HTTP mapping of every refusal, and image bytes with MIME, including the 404 for a missing image.
- **Image client (automated).** `tests/test_image_client.py` covers base64 decode, usage extraction, missing usage and a missing image.
- **Persistence (automated, `db` marker).** `tests/db/test_repo_posters.py` covers:
  - the playbill round trip;
  - an image surviving a later playbill upsert;
  - a missing poster;
  - `GET /api/games` joining the poster.
- **Config (automated).** `tests/test_config.py::test_poster_defaults` / `::test_poster_quota_bounds`. `tests/test_web_auth.py` covers `poster_images_enabled` in the public config.
- **Migration (Demo Contract for `db/migrations/`).** Run `alembic upgrade head` against a scratch database and paste the `story_posters` schema in the PR.
- **Web demo (Demo Contract for `interfaces/web/`).** Boot the app and screenshot the library with a drawn playbill, a painted poster, a legacy plain card and a Russian story.
- **Spend check after enabling (inspection).** After the first real paintings, compare the `PosterIllustrator` cost in the admin report with the OpenAI usage dashboard.
- **Standard gauntlet.** ruff, format, flake8, mypy, pytest.

## Related files

- `interfaces/web/playbill.py`, `interfaces/web/library_rows.py`, `interfaces/web/schemas_library.py`
- `interfaces/web/service.py` (`start_game_for_player` → `save_playbill`)
- `interfaces/web/poster_art.py`, `interfaces/web/poster_errors.py`, `interfaces/web/service_poster.py`, `interfaces/web/routes_poster.py`, `interfaces/web/app.py`
- `interfaces/web/auth_routes.py` (`poster_images_enabled` in public config)
- `interfaces/web/static/app.js`, `interfaces/web/static/style.css`
- `interfaces/web/beta_policy.py`, `interfaces/web/quota_locks.py`
- `llm/image_client.py`
- `db/tables.py` (`story_posters`), `db/repo_posters.py`, `db/repo_web_games.py`
- `alembic/versions/a9b0c1d2e3f4_add_story_posters.py`
- `config.py`, `.env.example`, `costs/model_pricing.py`
- `safety/factory.py`
- `tests/test_web_playbill.py`, `tests/test_web_poster.py`, `tests/test_web_poster_routes.py`, `tests/test_image_client.py`, `tests/db/test_repo_posters.py`, `tests/test_config.py`, `tests/test_web_auth.py`, `tests/_poster_helpers.py`
- `docs/decisions/0019-player-ui-stage-visual-language.md`
- `docs/decisions/0006-content-safety-moderation-pipeline.md`
- `docs/decisions/0006-player-dashboard-gui.md` (§5 single name-gating path)
- `docs/studio/09-founder-decision-register.md` (D004, D006, D007, D010)
- `docs/studio/11-friends-beta-onboarding.md` (privacy / beta disclaimer)
