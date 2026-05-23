# Storyteller Repo Briefing

Date: 2026-05-23
Repo: /home/max/Code/storyteller
Remote: https://github.com/MaksimKravchuk/storyteller.git
Branch: main tracking origin/main
Working tree at inspection: clean

## Product

Storyteller is an AI-powered text quest engine with a theater-style multi-agent architecture. The game creates interactive text adventures from a requested historical or fictional setting. A Director agent coordinates specialized performer agents for research, scene construction, NPC generation, narration, memory, and consistency.

## Current shape

Primary stack:
- Python 3.11+
- uv package/dependency management
- FastAPI web UI at interfaces/web/app.py
- aiohttp admin service
- optional Telegram bot
- async SQLAlchemy + asyncpg + Alembic
- PostgreSQL in docker-compose
- NetworkX knowledge graph
- OpenAI / Anthropic / OpenRouter / DeepSeek LLM clients
- Fly.io deployment via Dockerfile and fly.toml

Approximate size from local inspection:
- 501 Python files excluding alembic/cache/venv
- ~64k Python lines
- tests are large and mature: ~36k test lines, 173 top-level test Python files plus db/e2e/benchmark areas

Important modules:
- cast/: Director and performer agents
- engine/: public GameEngine API and factory
- models/: domain models
- knowledge/: scoped knowledge graph
- timeline/: game clock and events
- llm/: provider abstraction
- prompts/: composable prompt templates
- db/: persistence and ORM/domain converters
- interfaces/: web, admin, Telegram
- benchmarks/: narration-quality benchmark harness

## Existing commands

Install:
```bash
uv sync --group dev --extra openai --extra anthropic
```

Run CLI game:
```bash
uv run python main.py
```

Run player web UI:
```bash
uv run uvicorn interfaces.web.app:app --reload --host 127.0.0.1 --port 8070
```

Run full local stack:
```bash
docker compose up -d
# Web UI: http://localhost:8070
# Admin:  http://localhost:8080
docker compose down
```

Quality gate before commits:
```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run flake8 . && \
uv run mypy . && \
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
```

E2E, paid LLM/API-key required:
```bash
uv run pytest tests/e2e/ --alluredir=allure-results -v
```

Benchmarks, paid LLM/API-key required:
```bash
uv run python -m benchmarks run
```

## CI/CD

GitHub Actions workflows present:
- .github/workflows/ci.yml
- .github/workflows/benchmark.yml
- .github/workflows/claude-code-review.yml
- .github/workflows/claude.yml

Main CI jobs:
- lint: ruff, ruff format check, flake8/wemake
- test: pytest with coverage and Allure unit results
- test-db: Postgres/testcontainers DB tests
- e2e: paid LLM e2e tests on push or non-draft PRs
- deploy: Fly.io deploy on push to main after lint/test/test-db
- publish-allure: publish Allure history to gh-pages

## Release posture

This is already more than a toy prototype. It has:
- real web/admin surfaces
- persistence
- Docker/Fly deployment
- benchmark harness
- CI and coverage gates
- explicit coding discipline in CLAUDE.md

The next release should be run like a product release, not a code-only milestone.

## Main risks

1. LLM cost and nondeterminism
   - E2E and benchmark tests hit paid providers.
   - Release gates need clear separation between cheap unit tests, paid checks, and benchmark runs.

2. Product quality is hard to measure
   - Narrative quality is subjective. Keep benchmark scenarios and release-over-release comparison central.

3. Multi-agent prompt regressions
   - Past guidance already notes consumer-side prompt wiring regressions. Reviews must inspect prompt boundaries, not just domain objects.

4. Deployment risk
   - Main branch push deploys to Fly.io. Agents must never push directly to main without explicit human approval.

5. Secret/publishing risk
   - API keys, Telegram token, Fly token, and GitHub secrets must stay outside chat and code.

6. Scope risk
   - The game can expand infinitely. A release charter with explicit non-goals is mandatory.

## Immediate studio setup recommendation

Start with a release-planning sprint before creating many code tasks:
1. Define the next public target: demo, beta, or early-access-style web release.
2. Audit current live/deploy status and the player web UI experience.
3. Create a milestone backlog around release gates.
4. Use Hermes profiles as a small studio: producer, gameplay engineer, QA, release engineer, narrative evaluator, marketing/community.
