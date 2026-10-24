# ADR-0021: Gate the admin dashboard on the account admin role; switch player login to email + password

Date: 2026-10-24
Status: Accepted
Decision owner: Max
Related: D002 (Supabase Auth) in `docs/studio/09-founder-decision-register.md`, PR #361 (audit fix that made `ADMIN_TOKEN` mandatory on Fly), `docs/studio/08-fly-release-rollback.md`

## Context

Before this change the admin dashboard (aiohttp, port 8080) was protected by one shared secret, `ADMIN_TOKEN`. The middleware compared `Authorization: Bearer <token>` against it. PR #361 made the compare constant-time and made `run_server.py` refuse to boot on Fly without the token, because an unset token left the admin API open to anyone.

A shared token has the usual problems. It doesn't identify who acted. Revoking it means rotating it for everyone. It is one more Fly secret to manage, and it is pasted into a browser by hand. Meanwhile the Friends Beta already has real identities: Supabase Auth (D002) issues JWTs, `interfaces/web/auth.py` verifies them, and the `accounts` table already had an `is_admin` boolean column (`db/tables.py`) that nothing enforced.

The player login used Supabase magic links (`signInWithOtp`). Every login meant a round trip through email. The admin dashboard needs a direct sign-in to a Supabase session, and running two different login styles for one account would be confusing.

## Decision

1. **The admin API is gated by the account admin role, not a shared token.** `interfaces/admin.py`'s `_auth_middleware` calls `interfaces/admin_auth.admin_denial()` for every `/api/*` route when beta auth is on. It verifies the bearer token as a Supabase JWT (`verify_supabase_token`) and looks up the account by `supabase_user_id`. It returns **401** for a missing or invalid token and **403** when the account is missing or has `is_admin = false`. `ADMIN_TOKEN` and `AUTH_TOKEN_KEY` are removed.
2. **The dashboard signs the admin in with Supabase email + password.** It gets the browser-safe Supabase URL and publishable key from the unauthenticated `GET /config/public` route on the admin server. It sends the session's access token as the bearer.
3. **The boot guard changes from "token set" to "auth on".** `run_server.require_admin_auth_on_fly()` exits on Fly unless `BETA_AUTH_REQUIRED=true`. When auth is off (local dev), the admin API is open, the same as the old unset-token behaviour off Fly.
4. **Admins are granted by hand in SQL.** The account must have logged in to the player UI once so that its `accounts` row exists. Then run `UPDATE accounts SET is_admin = true WHERE email = ...` (documented in `docs/studio/08-fly-release-rollback.md`). There is no self-service admin grant and no grant UI.
5. **Player login switches from magic link to Supabase email + password, with reset.** `interfaces/web/static/app.js` uses `signInWithPassword` and `signUp` (with email confirmation when Supabase requires it). "Forgot password?" calls `resetPasswordForEmail`. The recovery link (`type=recovery` in the URL hash) opens a "choose a new password" form that calls `updateUser`. Supabase still owns password storage, hashing, reset emails and session issuance.

## Rationale

- **One identity system.** Admin access uses the same Supabase identity and JWT verification as player access. A stolen or leaked credential is tied to one person and can be revoked by flipping one column, with no secret rotation or redeploy.
- **Uses what already existed.** `accounts.is_admin` and `verify_supabase_token` were already there. The change deletes a secret and a code path, and it needs no migration.
- **Fails closed where it matters.** The Fly boot guard keeps the guarantee from PR #361 (no public admin API in production). It now ties that guarantee to the auth flag that controls player access too.
- **Password login is in line with D002.** D002 picked Supabase so that Storyteller would not own password-reset or security workflows. Supabase still does all of that. Email + password is one of the methods D002 expected; it rejected Google-only login partly because it "excludes testers who prefer email/password". Logging in without a trip to the inbox also makes returning to a game smoother, and lets admins and players use the same form of credential.

## Alternatives considered

### Alternative 1: Keep `ADMIN_TOKEN` (optionally alongside the role check)

This was already shipped and hardened in PR #361. It was rejected because a shared token gives no attribution and no per-person revocation. Keeping it as a second path also keeps a bypass around the role check, which is the weaker of the two to leak.

### Alternative 2: A separate admin allowlist (env var of emails or Supabase user IDs)

No DB write is needed to grant access. It was rejected because it duplicates `accounts.is_admin`, which already exists, and every change to the admin set would need a secrets change and a restart.

### Alternative 3: Supabase custom claims / `app_metadata.role` in the JWT

This would avoid a DB lookup per admin request. It was rejected for now because it needs Supabase-side hooks or service-role writes to manage roles, and it moves authority out of Storyteller's own `accounts` table. Admin traffic is tiny, so one lookup per request costs nothing.

### Alternative 4: Keep magic links for players and use passwords only for admins

This would change the fewest player-facing things. It was rejected because one account would then have two login styles, and testers kept paying the email round trip on every login.

### Alternative 5: OAuth (Google/GitHub) for login

There would be no passwords at all. It was rejected because D002 already turned down OAuth-only for excluding email/password testers, and it adds provider configuration that the beta doesn't need.

## Consequences

Positive consequences:
- One fewer production secret. Admin actions are tied to a real account.
- Admin access is granted or revoked with a single SQL update, with no redeploy.
- Players log in without a trip to their inbox and can reset a forgotten password themselves.

Tradeoffs / risks:
- **Admin access now depends on Supabase being up and on JWKS fetches succeeding.** If Supabase is down, admins are locked out along with players.
- **Granting is manual SQL.** The first admin has to bootstrap through a DB shell, and there is no audit trail of grants apart from DB logs.
- **Local dev with `BETA_AUTH_REQUIRED=false` leaves the admin API open.** This is intentional and matches the old behaviour off Fly. The Fly boot guard is the only thing preventing it in production.
- **Passwords bring credential-stuffing and weak-password risk.** Supabase's rate limits and its password policy are the mitigation. The client enforces only `minlength=6`.
- **The password-reset and email-confirmation redirects need the deployment origin allowed in Supabase's redirect URL settings.** If it isn't, the reset links break.
- Existing magic-link-only users have no password. They must use "Forgot password?" (or sign up again) before their first password login.

What future agents must preserve:
- Do not reintroduce a shared admin token or any admin bypass that skips the `accounts.is_admin` check.
- Every new admin route must live under `/api/` (or be explicitly gated) so the middleware covers it. Only `/config/public` and the dashboard HTML shell may be unauthenticated, and `/config/public` must expose only browser-safe values (Supabase URL, publishable key, auth flag). Never expose the service-role key or JWT secret.
- Keep the Fly boot guard: production must not start with beta auth off.
- Keep 401 (no valid session) separate from 403 (valid session, not an admin). The dashboard relies on 403 to show "This account does not have the admin role."
- Password storage, hashing and reset stay with Supabase. Do not add Storyteller-owned password handling (D002).
- Changing who can become an admin, or adding a self-service or UI grant path, is an approval-authority change. Get Max's sign-off first.

## Verification / tests

- `tests/test_admin_auth.py`: a missing or invalid token gives 401, a non-admin or missing account gives 403, an admin account passes, and `/config/public` returns only public values. The auth-off (no gate) path is covered implicitly by the other admin route tests, which run with beta auth off.
- `tests/test_run_server_admin_auth.py`: Fly without beta auth exits, and Fly with beta auth boots.
- `tests/test_admin.py`, `tests/test_admin_lifecycle.py`, `tests/test_admin_routes_settings*.py`: `AdminServer` is built without a `token` argument.
- `tests/test_web_auth.py`: the player shell includes the password, reset and new-password controls, and `/api/config/public` exposes only public Supabase values.
- Manual: sign in to the admin dashboard with an `is_admin` account (data loads) and with a non-admin account (role message shown). Run the player "Forgot password?" flow end to end against the Supabase project.

## Related files

- `interfaces/admin_auth.py`
- `interfaces/admin.py`
- `interfaces/admin_dashboard.html`
- `interfaces/admin_route_helpers.py`
- `interfaces/web/auth.py`
- `interfaces/web/static/app.js`, `interfaces/web/static/index.html`
- `run_server.py`
- `db/tables.py` (`accounts.is_admin`)
- `docs/studio/08-fly-release-rollback.md`
