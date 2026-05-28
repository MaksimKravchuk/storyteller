# M1 Release Candidate Baseline Report

Date: 2026-05-23
Repo: /home/max/Code/storyteller

## Summary

Result: PASS for local quality baseline and Docker Compose health smoke.

This baseline did not run paid LLM e2e tests or benchmarks.

## Quality baseline

Initial unit-test attempt failed during collection because the local uv environment did not yet include the anthropic extra:

```text
ModuleNotFoundError: No module named 'anthropic'
```

Resolution:

```bash
uv sync --group dev --extra openai --extra anthropic
```

After syncing extras, the quality baseline passed.

Commands/results:

```bash
uv run ruff check .
# PASS: All checks passed

uv run ruff format --check .
# PASS: 501 files already formatted

uv run flake8 .
# PASS: no output

uv run mypy .
# PASS: Success: no issues found in 500 source files

uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
# PASS: 1774 passed, 5 skipped, 66 deselected, 106 warnings in 8.89s
```

Warnings observed:
- aiohttp `NotAppKeyWarning` in `interfaces/admin.py` for app keys.
- one RuntimeWarning in `tests/test_admin_lifecycle.py` around an AsyncMock coroutine not awaited.

These warnings are not current release blockers, but they are good P2 cleanup candidates.

Logs:
- /tmp/storyteller-m1-quality-baseline.log
- /tmp/storyteller-m1-quality-baseline-retry.log

## Docker Compose smoke

Initial Docker Compose attempt failed because `.env` did not exist:

```text
env file /home/max/Code/storyteller/.env not found
```

Resolution:

```bash
cp .env.example .env
```

`.env` is gitignored.

Docker Compose result:

```bash
docker compose up -d
# PASS: image built, postgres healthy, storyteller started

curl -fsS http://localhost:8070/healthz
# PASS: {"status":"ok"}

curl -fsS http://localhost:8080/healthz
# PASS: {"status": "ok"}

docker compose ps
# PASS: postgres healthy, storyteller healthy

docker compose down
# PASS: containers/network removed
```

Runtime notes:
- Alembic migrations ran successfully.
- Admin dashboard started on port 8080.
- Web UI health endpoint passed on port 8070.

Logs:
- /tmp/storyteller-m1-docker-smoke.log
- /tmp/storyteller-m1-docker-smoke-retry-start.log
- /tmp/storyteller-m1-docker-smoke-retry-health.log

## Baseline conclusion

The repo is in strong release-candidate shape for non-paid checks:
- static checks pass
- type check passes
- unit tests pass
- Docker image builds
- local web/admin healthchecks pass
- database migrations apply cleanly

## Recommended next tasks

1. Convert the initial backlog into GitHub issues and labels.
2. Choose the release target in docs/studio/01-release-charter.md.
3. Define the 3 canonical demo scenarios in docs/studio/03-release-checklist.md.
4. Run paid LLM e2e/benchmark checks only after Max approves API cost.
5. Create a small issue for warning cleanup:
   - aiohttp AppKey warnings
   - AsyncMock RuntimeWarning
