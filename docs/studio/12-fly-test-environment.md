# Fly.io Test Environment Runbook

This runbook describes the on-demand Fly.io test environment used to run Storyteller's deterministic test suite in a disposable Fly Machine.

## Purpose

Use this environment when you want a clean Linux container that matches Storyteller's Docker packaging more closely than a developer laptop, without keeping an always-on VPS alive.

- Platform: Fly.io Machines
- Region: Amsterdam (`ams`) by default
- VM size: `shared-cpu-1x`, `1gb`
- Config: `fly.test.toml`
- Image: `Dockerfile.test`
- Trigger: GitHub Actions workflow `Fly test environment`

The workflow deploys the current commit to a dedicated Fly test app, runs a pytest command over `flyctl ssh console`, and scales the app to zero by default when finished.

Do not use the production app `storyteller-quest` for this workflow.

## What it runs

Default deterministic command:

```bash
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks --ignore=tests/db -m 'not db and not benchmark and not live' -v
```

Optional live-provider e2e command, enabled with the workflow input `run_live_e2e=true`:

```bash
uv run pytest tests/e2e/ --alluredir=allure-results -v
```

The DB-backed `tests/db/` suite is intentionally excluded from the default Fly command because those tests use Testcontainers and need a Docker daemon. Fly Machines run Docker-built containers, but they are not provisioned as privileged Docker-in-Docker hosts. Keep `tests/db/` in the existing GitHub-hosted `CI / test-db` job, which has Docker available.

## One-time provisioning

You need a Fly access token with permission to create/manage the test app.

1. Choose an app name. Recommended:

   ```text
   storyteller-test
   ```

2. Add repository configuration in GitHub:

   Repository secret:

   - `FLY_API_TOKEN` — Fly token used by `flyctl`.

   Repository variable or secret:

   - `FLY_TEST_APP` — dedicated test app name, for example `storyteller-test`.

   Optional repository variables:

   - `FLY_ORG` — Fly organization slug; defaults to `personal`.
   - `FLY_TEST_REGION` — Fly region; defaults to `ams`.

   Optional repository secrets, only required for live-provider tests:

   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `OPENROUTER_API_KEY`
   - `DEEPSEEK_API_KEY`
   - `TAVILY_API_KEY`

3. Run the GitHub Actions workflow manually:

   GitHub UI:

   - Actions
   - Fly test environment
   - Run workflow

   GitHub CLI:

   ```bash
   gh workflow run "Fly test environment" \
     --repo MaksimKravchuk/storyteller \
     --ref main
   ```

   The workflow creates the Fly app if it does not exist, sets the region, stages optional runtime secrets, deploys the current commit with `Dockerfile.test`, runs the test command, and scales the app to zero.

## Running a custom command

Use the `test_command` workflow input for targeted checks:

```bash
gh workflow run "Fly test environment" \
  --repo MaksimKravchuk/storyteller \
  --ref main \
  -f test_command='uv run pytest tests/test_web_api.py -v'
```

Run live e2e tests only when provider API cost is approved:

```bash
gh workflow run "Fly test environment" \
  --repo MaksimKravchuk/storyteller \
  --ref main \
  -f run_live_e2e=true
```

## Start, stop, suspend, and teardown

The workflow scales the app to zero at the end by default (`suspend_after=true`). Manual commands:

```bash
# Inspect current state
flyctl status --app "$FLY_TEST_APP"

# Start/resume one test Machine after it was scaled to zero
flyctl scale count 1 --app "$FLY_TEST_APP"

# Stop/suspend to avoid idle cost
flyctl scale count 0 --yes --app "$FLY_TEST_APP"

# Destroy the environment completely
flyctl apps destroy "$FLY_TEST_APP" --yes
```

Cost-control default: keep `suspend_after=true` unless you are actively debugging the machine.

## Troubleshooting

- `FLY_TEST_APP must not be the production storyteller-quest app`: set `FLY_TEST_APP` to a dedicated test app.
- `Set the FLY_API_TOKEN GitHub Actions secret`: add or rotate the repository secret.
- `flyctl ssh console` cannot connect: check `flyctl status --app "$FLY_TEST_APP"` and rerun the workflow with `suspend_after=false` for debugging.
- Provider tests skip or fail preflight: confirm the matching provider key is configured as a GitHub Actions secret and staged into the Fly app by the workflow.
- DB-backed tests are needed: run the existing `CI` workflow or `test-db` job; do not move those tests to Fly unless the DB tests are changed to use an external Postgres fixture instead of Testcontainers.
