# Fly.io Release and Rollback Procedure

Issue: #202
Release target: Public Web Demo v0.1
App: `storyteller-quest`
Primary URL: `https://storyteller-quest.fly.dev`
Admin URL: `https://storyteller-quest.fly.dev:8080`

This procedure is for preparing and operating the Fly.io deployment. Agents may prepare release artifacts, checks, branches, and pull requests, but must not publish a public deploy or merge a deploy-triggering change to `main` without explicit approval from Max.

## Deployment model

- Runtime config lives in `fly.toml`.
- The Docker image runs `uv run python run_server.py`.
- `run_server.py` applies Alembic migrations, starts the admin dashboard on port 8080, and starts the player web UI on port 8070.
- GitHub Actions deploys on push to `main` when the `CI` workflow runs and the `lint`, `test`, and `test-db` jobs pass.
- The `CI` workflow ignores docs-only changes, so this documentation PR by itself does not publish a Fly deploy.
- The deploy job runs `flyctl deploy --remote-only` with the GitHub Actions secret `FLY_API_TOKEN`.

## Required secret names

List names only. Never paste or log values.

GitHub Actions repository secrets:

- `FLY_API_TOKEN`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `SUPABASE_DB_URL` — Supabase session-pooler connection string, used only by `supabase-keepalive.yml` so the Free-plan project is not paused for inactivity.

Fly app secrets / runtime environment:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `BETA_AUTH_REQUIRED=true` plus the `SUPABASE_*` auth settings — the boot refuses to start on Fly without beta auth, because the admin dashboard is gated by the account admin role (there is no admin token).

Granting the admin role: the account must have logged in to the player UI once, then

```sql
UPDATE accounts SET is_admin = true WHERE email = 'you@example.com';
```

Log in to the admin dashboard with the same email and password.

Optional Fly app secrets / runtime environment, depending on enabled providers:

- `OPENROUTER_API_KEY`
- `DEEPSEEK_API_KEY`
- `DIRECTOR_MODEL`
- `AGENT_MODEL`
- `NARRATOR_MODEL`
- `DRAMATURGE_MODEL`
- `DRAMATURGE_ENABLED`
- `WEB_PORT`

## Pre-release checklist

1. Confirm Max has approved publishing this release candidate.
2. Confirm the release PR is reviewed and ready to merge.
3. Confirm the full local quality gate has passed or any waiver is explicitly recorded:

   ```bash
   uv run ruff check . && \
   uv run ruff format --check . && \
   uv run flake8 . && \
   uv run mypy . && \
   uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
   ```

4. Confirm CI is green on the release PR, or explicitly record that the workflow was skipped because the change was docs-only.
5. Confirm any paid e2e or benchmark checks were run only after Max approved API cost.
6. Confirm the Fly app exists and `fly.toml` still targets `storyteller-quest`.
7. Confirm required secret names are present without exposing values:

   ```bash
   flyctl secrets list --app storyteller-quest
   ```

8. Confirm current deployed release before changing anything:

   ```bash
   flyctl releases --app storyteller-quest
   flyctl status --app storyteller-quest
   ```

## Release procedure

Preferred path: merge the reviewed release PR after Max approval, then let GitHub Actions deploy from `main`.

1. Get explicit Max approval to publish.
2. Squash-merge the approved PR to `main`.
3. Watch the `CI` workflow on `main`; the `deploy` job should run only after `lint`, `test`, and `test-db` pass.
4. Verify the new Fly release:

   ```bash
   flyctl releases --app storyteller-quest
   flyctl status --app storyteller-quest
   flyctl logs --app storyteller-quest
   ```

5. Smoke-test the public surfaces:

   ```bash
   curl -fsS https://storyteller-quest.fly.dev/healthz
   curl -kfsS https://storyteller-quest.fly.dev:8080/healthz
   ```

6. Open the player URL in a browser and run the release checklist gameplay smoke gate.
7. Record the deployed Fly release version, commit SHA, smoke-test result, and any known limitations in the release notes or PR thread.

Manual deploy path, only if GitHub Actions is unavailable and Max approves it:

```bash
flyctl deploy --remote-only --app storyteller-quest
```

Then run the same verification and smoke checks listed above.

## Rollback procedure

Use this when the public deployment is unhealthy or has a severe player-facing regression.

1. Stop and capture evidence first if doing so does not worsen impact:

   ```bash
   flyctl status --app storyteller-quest
   flyctl logs --app storyteller-quest
   curl -fsS https://storyteller-quest.fly.dev/healthz
   curl -kfsS https://storyteller-quest.fly.dev:8080/healthz
   ```

2. List releases and choose the last known-good release version:

   ```bash
   flyctl releases --app storyteller-quest
   ```

3. Roll back to that version:

   ```bash
   flyctl releases rollback <version> --app storyteller-quest
   ```

4. Verify the rollback:

   ```bash
   flyctl status --app storyteller-quest
   flyctl releases --app storyteller-quest
   curl -fsS https://storyteller-quest.fly.dev/healthz
   curl -kfsS https://storyteller-quest.fly.dev:8080/healthz
   ```

5. Check logs for continuing startup, database, or provider errors:

   ```bash
   flyctl logs --app storyteller-quest
   ```

6. Post the rollback result in the release PR or incident thread, including the failed release version, the restored version, healthcheck result, and any follow-up issue links.

## Safety notes

- Never paste secret values into GitHub issues, PRs, logs, comments, or chat.
- Do not run `flyctl deploy` for the public app without Max approval.
- Do not push directly to `main`; `main` pushes trigger the production deploy workflow for non-docs changes.
- Treat Alembic migrations as forward-only unless a rollback plan explicitly handles schema compatibility.
- If the rollback fails or the database state is incompatible, leave the app in the safest available state and escalate to Max immediately.
