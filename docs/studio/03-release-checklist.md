# Storyteller Release Checklist

Use this for every release candidate.

## 1. Scope gate

- [ ] Release target named, e.g. Public Web Demo v0.1
- [ ] Must-have scope listed
- [ ] Non-goals listed
- [ ] No untriaged P0/P1 issues
- [ ] Max has approved the scope

## 2. Repository gate

- [ ] Working tree clean
- [ ] Release branch/PR exists; no direct main push by agents
- [ ] PR description includes summary and test evidence
- [ ] Version/tag decision made
- [ ] Changelog/release notes drafted

## 3. Quality gate

Run before commit/merge:

```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run flake8 . && \
uv run mypy . && \
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
```

- [ ] Ruff lint passes
- [ ] Ruff format check passes
- [ ] Flake8/wemake passes
- [ ] Mypy passes
- [ ] Unit tests pass
- [ ] Coverage gate respected
- [ ] DB tests pass in CI

## 4. Paid/LLM quality gate

Only run with explicit cost/API-key approval:

```bash
uv run pytest tests/e2e/ --alluredir=allure-results -v
uv run python -m benchmarks run
```

- [ ] E2E tests pass or failures are triaged
- [ ] Benchmark run archived
- [ ] Narrative quality report reviewed
- [ ] Any severe coherence regressions addressed or waived

## 5. Local runtime gate

```bash
docker compose up -d
# Web UI: http://localhost:8070
# Admin:  http://localhost:8080
docker compose down
```

- [ ] Docker image builds
- [ ] Postgres healthcheck passes
- [ ] Web UI healthcheck passes
- [ ] Admin healthcheck passes
- [ ] Server logs contain no obvious startup errors

## 6. Gameplay smoke gate

For each canonical scenario:

- [ ] Start a new story
- [ ] Play 5+ turns
- [ ] Talk to an NPC
- [ ] Explore/move/inspect at least once
- [ ] Confirm memory of a recent event appears later
- [ ] Confirm no raw traceback appears in UI
- [ ] Capture notes/screenshots if something feels off

Canonical scenario slots:
1. Historical grounded setting: ______________________________
2. Fictional/fantasy setting: ________________________________
3. Weird edge-case setting: __________________________________

## 7. Deployment gate

- [ ] Fly secrets present and current
- [ ] Deploy workflow is green or manual deploy succeeds
- [ ] Production healthcheck passes
- [ ] Demo URL opens
- [ ] Rollback path documented

## 8. Launch gate

- [ ] README quickstart accurate
- [ ] Demo URL or access instructions accurate
- [ ] Known limitations documented
- [ ] Release notes ready
- [ ] Announcement/social copy ready
- [ ] Feedback channel ready

## 9. Human approval

- [ ] Max plays release candidate
- [ ] Max approves publishing
- [ ] Release tag created
- [ ] Public announcement posted
