# Hermes Company Setup for Storyteller

Current Hermes state at planning time:
- Only profile present: default
- Gateway: running
- Repo path: /home/max/Code/storyteller

## Recommended profiles

Create the studio profiles:

```bash
hermes profile create gameproducer --clone default
hermes profile create gameplayengineer --clone default
hermes profile create qaplaytester --clone default
hermes profile create buildreleaseengineer --clone default
hermes profile create narrativeevaluator --clone default
hermes profile create marketingcommunity --clone default
```

Optional later:

```bash
hermes profile create promptengineer --clone default
hermes profile create dbpersistenceengineer --clone default
hermes profile create webuiengineer --clone default
```

## Suggested profile prompts / duties

### gameproducer

System role:
You are the Storyteller producer. You decompose work, maintain release scope, create issues/cards, track blockers, and report status. Do not implement code yourself unless explicitly assigned. Enforce release gates and ask Max for taste/product decisions.

### gameplayengineer

System role:
You are the Storyteller gameplay engineer. You work on cast/, engine/, models/, knowledge/, timeline/, and tests. Follow strict TDD for bugs. Keep changes surgical. Never push to main. Run the quality gate before commit.

### qaplaytester

System role:
You are the Storyteller QA playtester. You reproduce bugs, write regression tests, run smoke checks, and prepare release-candidate reports. Prefer consumer-side integration tests over supplier-only assertions.

### buildreleaseengineer

System role:
You are the Storyteller build and release engineer. You own CI, Docker, Fly.io, release tags, rollback docs, and GitHub Actions failures. Never publish or deploy outside approved release flow without Max approval.

### narrativeevaluator

System role:
You are the Storyteller narrative evaluator. You design benchmark scenarios, inspect prompt wiring, evaluate narrative quality, and catch memory/coherence regressions. Ask before running paid LLM benchmarks.

### marketingcommunity

System role:
You are the Storyteller marketing/community operator. You draft release notes, README copy, demo announcements, known-limitations text, and feedback prompts. You do not change product behavior directly.

## Work routing options

### Option A: Lightweight mode

Use this current Hermes session and delegate_task for research/review/implementation subtasks. Best for the next few planning steps.

Pros:
- Fast to start
- No extra config
- Good for repo audit and first roadmap

Cons:
- Not durable across restarts
- Less visible project-management trail

### Option B: GitHub Issues as source of truth

Use GitHub Issues and PRs for all tasks. Agents work issue-by-issue.

Pros:
- Natural for private GitHub repo
- PR/CI/release integration
- Good audit trail

Cons:
- gh CLI is not installed currently
- Need GitHub token or gh auth for full automation

Recommended setup:
```bash
# install gh using your OS package manager, then:
gh auth login
gh auth setup-git
```

### Option C: Hermes Kanban + GitHub PRs

Use Hermes Kanban for multi-profile dispatch, but link implementation output to GitHub PRs.

Pros:
- Closest to “agent company” model
- Durable queue and worker profiles
- Good for parallel roles

Cons:
- Requires Kanban setup and profile discipline

Recommended mature setup:
- Kanban cards for internal routing
- GitHub issues for externally visible backlog
- GitHub PRs for all code changes
- Cron jobs for daily/weekly reporting

## Suggested cron jobs

Daily producer standup:
```text
Schedule: every weekday 10am
Workdir: /home/max/Code/storyteller
Prompt: Inspect git status, recent commits, open local changes, GitHub status if available, CI state if available, and docs/studio roadmap. Summarize blockers and recommend the next three tasks. Do not modify files.
```

Weekly release readiness:
```text
Schedule: every Friday 4pm
Workdir: /home/max/Code/storyteller
Prompt: Compare the repo state against docs/studio/03-release-checklist.md. Produce go/no-go, missing evidence, top risks, and recommended next actions. Do not publish or deploy.
```

## Immediate next step

Use lightweight mode to run M1: release candidate baseline.

Recommended first command set:
```bash
cd /home/max/Code/storyteller
uv run ruff check .
uv run ruff format --check .
uv run flake8 .
uv run mypy .
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
```

Then run Docker Compose smoke checks:
```bash
docker compose up -d
curl -fsS http://localhost:8070/healthz
curl -fsS http://localhost:8080/healthz
docker compose logs --tail=100 storyteller
docker compose down
```
