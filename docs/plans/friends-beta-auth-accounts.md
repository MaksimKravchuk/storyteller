# Implementation Plan: Supabase Auth, Invite Gate, Account-Owned Games, and My Stories

Release target: Friends Beta v0.2  
Issues: #237, #238, #239  
Status: Draft implementation plan  
Branch: `docs/friends-beta-v0-2-plan`

## Goal

Move the web beta from anonymous `web_player_id` cookie identity to authenticated Supabase accounts so invited testers can sign in, create account-owned stories, resume them across browsers/devices, and only see/manage their own stories.

## Current repo facts this plan depends on

- Anonymous web identity is currently minted in `interfaces/web/deps.py` as the `web_player_id` cookie.
- `db/tables.py` has `sessions.web_player_id`; `db/repo_sessions.py` exposes `create_web(web_player_id)` and `get_latest_web(web_player_id)`.
- Web routes in `interfaces/web/routes.py` depend on `get_player_id()` and pass `player_id` to `interfaces/web/service.py`.
- `interfaces/web/service.py` currently treats the latest web session as the active game and verifies `game_id` only after loading the caller's latest session.
- The web client is static vanilla HTML/JS in `interfaces/web/static/index.html` and `interfaces/web/static/app.js`.
- Existing tests for route wiring live in `tests/test_web_api.py`; DB session tests live in `tests/db/test_web_session.py`.

## Decisions and defaults

- Supabase Auth is the beta auth provider, per `docs/studio/09-founder-decision-register.md` D002.
- Gameplay APIs fail closed when beta auth is required: no valid user means no game creation, continuation, turn processing, or library access.
- Use Supabase access tokens in the `Authorization` bearer header for API calls. Do not rely on the public anon key for backend authorization.
- Store only the Supabase user id, email, and beta/account metadata needed by Storyteller.
- Keep `web_player_id` only as legacy/guest identity unless Max explicitly wants anonymous guest mode in the beta. Authenticated beta routes should use `account_id`.
- Use 404 for cross-user game ids to avoid leaking whether another user's game exists.

## Target data model

Add these tables/columns via Alembic and mirror them in `db/tables.py`:

1. `accounts`
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `supabase_user_id UUID UNIQUE NOT NULL`
   - `email TEXT NOT NULL`
   - `plan TEXT NOT NULL DEFAULT 'friend_beta'`
   - `is_admin BOOLEAN NOT NULL DEFAULT false`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - indexes: unique `supabase_user_id`; lower-email lookup index if practical.

2. `beta_invites`
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `email TEXT UNIQUE NOT NULL` stored normalized lowercase
   - `status TEXT NOT NULL DEFAULT 'invited'` with valid states `invited`, `accepted`, `revoked`
   - `invited_by TEXT NULL`
   - `invited_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - `accepted_at TIMESTAMPTZ NULL`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - indexes: lower-email lookup/status.

3. `sessions`
   - add `account_id UUID NULL REFERENCES accounts(id) ON DELETE CASCADE`
   - add `archived_at TIMESTAMPTZ NULL`
   - add `title TEXT NULL` for My Stories display; initially derive from setting when absent.
   - indexes: `idx_sessions_account_id_updated_at`, `idx_sessions_account_id_archived_at`.
   - keep `web_player_id` nullable for legacy rows and non-beta guest mode.

Migration policy:

- Do not attempt to guess ownership of existing anonymous-cookie sessions.
- Existing rows get `account_id = NULL` and remain invisible to authenticated beta library endpoints unless a later explicit migration/claim flow is approved.
- Telegram sessions continue to use `telegram_chat_id` and should not require `account_id`.

## Environment/config plan

Update `config.py` and `.env.example` with non-secret placeholders:

- `SUPABASE_URL`: public project URL, e.g. `https://<project-ref>.supabase.co`.
- `SUPABASE_PUBLISHABLE_KEY`: public browser key (format `sb_publishable_*`) used by `supabase-js`; safe to expose but do not hard-code real values. Legacy `SUPABASE_ANON_KEY` / `SUPABASE_KEY` are still accepted as fallbacks in `Config.public_supabase_key` for local dev.
- `SUPABASE_JWKS_URL`: optional override; default derived as `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`.
- `SUPABASE_JWT_AUDIENCE`: default `authenticated`.
- `SUPABASE_JWT_ISSUER`: optional override; default `{SUPABASE_URL}/auth/v1`.
- `BETA_AUTH_REQUIRED`: default `true` outside tests/local overrides.
- `BETA_INVITE_GATE_ENABLED`: default `true`.

Add readiness checks in `interfaces/web/readiness.py` so beta deploys report missing Supabase config as not ready when `BETA_AUTH_REQUIRED=true`.

## Implementation sequence

### PR 1 / Issue #237: Auth foundation and invite gate

#### 1. Add auth-focused tests first

Files:

- `tests/test_web_auth.py` new
- `tests/test_web_api.py` update only where route dependency expectations change
- `tests/db/test_accounts.py` new

Red tests to write before implementation:

1. `GET /api/me` returns 401 without `Authorization` when `BETA_AUTH_REQUIRED=true`.
2. `GET /api/me` returns 401 for malformed bearer tokens.
3. `GET /api/me` returns 403 for a valid Supabase token whose email is not invited.
4. `GET /api/me` returns account metadata for an invited user and creates/updates the local `accounts` row.
5. `POST /api/games` returns 401 unauthenticated and 403 uninvited; the service layer must not be called in either case.
6. DB test: invite lookup normalizes email case.
7. DB test: accepting an invite marks `accepted_at` and links/creates the account idempotently.

Verification while red:

```bash
uv run pytest tests/test_web_auth.py tests/db/test_accounts.py -v
```

Expected: failures showing missing routes/repos/deps, not unrelated collection failures.

#### 2. Add dependencies

Files:

- `pyproject.toml`
- `uv.lock`

Implementation:

- Add `PyJWT[crypto]` or equivalent maintained JWT/JWKS verifier.
- Keep `httpx` for JWKS fetches; it already exists in `pyproject.toml`.

Verification:

```bash
uv sync
uv run python -c "import jwt; print(jwt.__version__)"
```

#### 3. Add database schema and repository helpers

Files:

- `alembic/versions/<revision>_add_accounts_and_beta_invites.py` new
- `db/tables.py`
- `db/repo_accounts.py` new
- `db/repository.py`
- `tests/db/test_accounts.py`

Implementation:

- Define `accounts` and `beta_invites` tables.
- Add `AccountStore` under `repo.accounts` with:
  - `get_invite_by_email(email: str) -> dict | None`
  - `create_invite(email: str, invited_by: str | None = None) -> dict`
  - `get_by_supabase_user_id(supabase_user_id: str) -> dict | None`
  - `get_or_create_for_invited_user(supabase_user_id: str, email: str) -> dict`
  - `is_email_invited(email: str) -> bool`
- Normalize invite emails with `.strip().lower()` at repo boundaries.
- If invite status is `revoked`, deny access even if an `accounts` row exists.

Verification:

```bash
uv run pytest tests/db/test_accounts.py -v
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

#### 4. Implement Supabase JWT verification dependency

Files:

- `interfaces/web/auth.py` new
- `interfaces/web/deps.py`
- `interfaces/web/schemas.py`
- `interfaces/web/routes.py`
- `tests/test_web_auth.py`

Implementation:

- Add a small `AuthenticatedUser` dataclass/model containing:
  - `account_id: str`
  - `supabase_user_id: str`
  - `email: str`
  - `plan: str`
  - `is_admin: bool`
- Add `get_current_user(request, cfg, repo)` dependency:
  1. If `BETA_AUTH_REQUIRED=false`, allow explicit test/local bypass only via dependency override; do not silently mint account ids.
  2. Parse the `Authorization` bearer header.
  3. Fetch/cache Supabase JWKS using `SUPABASE_JWKS_URL` with short TTL.
  4. Verify JWT signature, issuer, audience, `exp`, and `sub`.
  5. Extract email from `email` claim or `user_metadata.email`; reject if absent.
  6. Check invite gate when `BETA_INVITE_GATE_ENABLED=true`.
  7. Create/update local account row and return `AuthenticatedUser`.
- Keep `get_player_id()` and `player_id_middleware` temporarily for legacy tests/guest mode, but new beta game routes should depend on `get_current_user`.
- Add `GET /api/me` returning `{email, plan, is_admin}` without exposing internal ids unless useful for diagnostics.

Verification:

```bash
uv run pytest tests/test_web_auth.py -v
```

#### 5. Add login/logout UI wiring

Files:

- `interfaces/web/static/index.html`
- `interfaces/web/static/app.js`
- `interfaces/web/static/style.css`
- `tests/test_web_api.py` static shell assertions or new `tests/test_web_auth_ui.py`

Implementation:

- Include `supabase-js` via CDN or vendored static asset; no build step.
- Add sign-in panel with email magic link or OAuth provider button, depending on configured Supabase method.
- Initialize client from server-provided config endpoint, not hard-coded values:
  - add `GET /api/config/public` returning `supabase_url`, `supabase_anon_key`, auth-required flags.
- Store Supabase session using the library default storage.
- Add `Authorization` header to all `/api/*` fetches when a Supabase session exists.
- Add logout button that clears Supabase session and hides game controls.
- Player-facing states:
  - unauthenticated: show sign-in, no setting/game form.
  - uninvited: show friendly beta invite message.
  - authenticated/invited: show My Stories/start flow.

Verification:

```bash
uv run pytest tests/test_web_api.py -k "index or config or auth" -v
```

### PR 2 / Issue #238: Account-owned sessions and cross-user isolation

#### 1. Add ownership tests first

Files:

- `tests/db/test_account_sessions.py` new
- `tests/test_web_api.py` or `tests/test_web_account_isolation.py` new

Red tests:

1. `repo.sessions.create_for_account(account_id)` creates a session with `account_id` and no `web_player_id`.
2. `repo.sessions.get_for_account(account_id, session_id)` returns the row only for the owner.
3. `repo.sessions.get_session_for_account_game(account_id, game_id)` returns owner row by `game_states.id` join.
4. Cross-user guessed `game_id` on `POST /api/games/{game_id}/actions` returns 404 and does not call the engine/process service for the wrong owner.
5. `GET /api/games/current` returns only the current user's newest non-archived game.
6. Existing `web_player_id` route tests are either updated to authenticated-account fixtures or explicitly scoped to guest mode.

Verification while red:

```bash
uv run pytest tests/db/test_account_sessions.py tests/test_web_account_isolation.py -v
```

#### 2. Extend session repository for account ownership

Files:

- `db/repo_sessions.py`
- `db/repo_admin.py` if admin listing should show account/email
- `db/tables.py`
- `tests/db/test_account_sessions.py`

Implementation:

- Add methods:
  - `create_for_account(account_id: str) -> dict`
  - `get_latest_for_account(account_id: str, include_archived: bool = False) -> dict | None`
  - `get_for_account(session_id: str, account_id: str) -> dict | None`
  - `get_for_account_game(account_id: str, game_id: str) -> dict | None`
  - `archive_for_account(session_id: str, account_id: str) -> bool`
- Update `update()` to bump `updated_at=clock_timestamp()` on state/language changes.
- Ensure all account methods filter `archived_at IS NULL` unless requested.

Verification:

```bash
uv run pytest tests/db/test_account_sessions.py tests/db/test_web_session.py -v
```

#### 3. Update web service to accept authenticated users

Files:

- `interfaces/web/service_helpers.py`
- `interfaces/web/service.py`
- `interfaces/web/routes.py`
- `tests/test_web_account_isolation.py`

Implementation:

- Replace route-level `PlayerIdDep` on gameplay APIs with `CurrentUserDep`.
- Change `StartGameParams.player_id` to `account_id` or add a new account-owned params model.
- In `start_game_for_player`, call `repo.sessions.create_for_account(user.account_id)` for beta routes.
- In `get_current_snapshot`, call `repo.sessions.get_latest_for_account(user.account_id)`.
- In `process_turn_for_player`, do not load latest session and compare game id. Instead:
  1. call `repo.sessions.get_for_account_game(user.account_id, game_id)`;
  2. if absent, raise `GameNotFoundError`;
  3. resume exactly that session id.
- Log failures with `account_id`/email, not Supabase tokens.

Verification:

```bash
uv run pytest tests/test_web_account_isolation.py tests/test_web_api.py -v
```

#### 4. Validate legacy/guest behavior explicitly

Files:

- `interfaces/web/deps.py`
- `interfaces/web/routes.py`
- `interfaces/web/service.py`
- `tests/test_web_api.py`

Implementation:

- Decide per config:
  - `BETA_AUTH_REQUIRED=true`: authenticated account routes only.
  - `BETA_AUTH_REQUIRED=false`: keep anonymous `web_player_id` routes for local smoke/dev if needed.
- Do not allow a request to choose arbitrary `account_id` or `web_player_id` from JSON.
- Keep cookie middleware only if guest mode remains needed; otherwise plan a later cleanup after beta is stable.

Verification:

```bash
uv run pytest tests/test_web_api.py -v
```

### PR 3 / Issue #239: My Stories game library

#### 1. Add API contract tests first

Files:

- `tests/test_web_my_stories.py` new
- `tests/db/test_game_library.py` new
- `interfaces/web/schemas.py`

Red tests:

1. `GET /api/games` returns only the authenticated user's non-archived games, newest updated first.
2. Response item includes `game_id`, `title`, `setting`, `turn_count`, `updated_at`, `created_at`, and `is_current` or equivalent.
3. User A cannot see User B's games in the list.
4. `GET /api/games/{game_id}` returns a snapshot for the owner and 404 for another user.
5. `POST /api/games/{game_id}/archive` archives only the owner's game; second call is idempotent or returns 404 by documented choice.
6. Archived games do not appear in default list and cannot receive new actions unless explicitly unarchived later.

Verification while red:

```bash
uv run pytest tests/test_web_my_stories.py tests/db/test_game_library.py -v
```

#### 2. Add repository list/select/archive support

Files:

- `db/repo_sessions.py`
- `db/repo_admin.py` optional
- `interfaces/web/schemas.py`
- `tests/db/test_game_library.py`

Implementation:

- Add `list_games_for_account(account_id, include_archived=False)` joining `sessions`, `game_states`, and `settings`.
- Prefer `sessions.title`; fallback to `settings.name` or a truncated setting summary.
- Use `sessions.updated_at` as library ordering; ensure turn processing touches session `updated_at` after successful persist.
- Add archive method from PR 2 if not already done.

Verification:

```bash
uv run pytest tests/db/test_game_library.py -v
```

#### 3. Add My Stories routes

Files:

- `interfaces/web/routes.py`
- `interfaces/web/service.py`
- `interfaces/web/schemas.py`
- `tests/test_web_my_stories.py`

Implementation:

- Add `GET /api/games` -> list library items for current account.
- Add `GET /api/games/{game_id}` -> load a specific owned game snapshot.
- Keep `POST /api/games` -> create a new owned game; do not replace existing games.
- Add `POST /api/games/{game_id}/archive` or `DELETE /api/games/{game_id}` with soft-delete semantics. Prefer `POST .../archive` for beta to avoid accidental destructive deletion.
- Keep `GET /api/games/current` as compatibility endpoint that returns newest non-archived game, or have the client use `GET /api/games` directly.

Verification:

```bash
uv run pytest tests/test_web_my_stories.py tests/test_web_account_isolation.py -v
```

#### 4. Add My Stories UI

Files:

- `interfaces/web/static/index.html`
- `interfaces/web/static/app.js`
- `interfaces/web/static/style.css`
- `tests/test_web_api.py` static shell assertions
- Optional e2e/smoke docs: `docs/qa/player-web-ui-smoke.md`

Implementation:

- Add a library panel shown after successful auth.
- On load:
  1. fetch `/api/me`;
  2. fetch `/api/games`;
  3. show existing stories with Continue and Archive buttons;
  4. show Start New Story form.
- Continue button calls `GET /api/games/{game_id}` and renders snapshot.
- New Story creates a new game and refreshes the library; it must not hide older stories permanently.
- Archive button calls archive endpoint, removes the item from default list, and if archiving current story returns player to library/start state.
- Empty state: “No stories yet. Start one.”
- Friendly unauthorized/uninvited messages must not expose raw HTTP/JWT errors.

Verification:

```bash
uv run pytest tests/test_web_api.py -k "index or stories" -v
```

## Cross-user isolation checklist

Before considering issues #237/#238/#239 done, verify all of these are covered by automated tests:

- User A cannot list User B's stories.
- User A cannot load User B's `game_id` snapshot.
- User A cannot post an action to User B's `game_id`.
- User A cannot archive User B's `game_id`.
- Unauthenticated users cannot create/list/load/action/archive games.
- Uninvited authenticated users cannot create/list/load/action/archive games.
- Revoked invite/account cannot continue consuming gameplay budget.
- Wrong-owner responses are 404, not 403, for game-specific routes.
- Auth failures are 401/403 and happen before LLM/engine calls.

## Manual QA script

Use staging/local with a real Supabase project or a controlled test project:

1. Configure env vars from `.env.example`; do not commit real values.
2. Add invite for `friend-a@example.com`; do not invite `friend-b@example.com`.
3. Sign in as Friend A.
4. Start Story A1 and play one turn.
5. Start Story A2 and confirm A1 still appears in My Stories.
6. Continue A1 and confirm transcript resumes.
7. Open a second browser/device, sign in as Friend A, and confirm A1/A2 appear.
8. Sign out.
9. Sign in as Friend B and confirm gameplay is blocked with invite message.
10. Attempt a copied Friend A `game_id` as Friend B and confirm 404/blocked behavior.
11. Archive A1 as Friend A and confirm it disappears from default My Stories and cannot receive actions.

## Quality gate

Run focused tests after each PR-sized slice, then the full local gate before commit/merge:

```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run flake8 . && \
uv run mypy . && \
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
```

If paid/model behavior is touched indirectly, also run the existing web smoke/e2e gate only with Max-approved credentials:

```bash
uv run pytest tests/e2e/ --alluredir=allure-results -v
```

## Done criteria

- Supabase Auth env/config is documented and readiness-gated.
- Backend verifies Supabase JWTs server-side and maps valid invited users to local accounts.
- Invite/allowlist gate blocks uninvited users before any game or LLM work.
- Sessions are account-owned for beta users.
- Cross-user route access is isolated by repository query, not only by route checks.
- My Stories lets a tester list, continue, create, and archive their own stories.
- Existing anonymous `web_player_id` behavior is either confined to explicit guest/dev mode or left only as legacy data support.
- Focused auth/account/library tests and full quality gate pass.
