# AGENTS.md

Repository-specific instructions for AI agents working on Storyteller.

## Project

Storyteller is an AI-powered text quest engine using a theater-style multi-agent architecture. The Director coordinates performer agents for research, scene building, NPC generation, narration, memory, and consistency.

## Required commands

Install:
```bash
uv sync --group dev --extra openai --extra anthropic
```

Run web UI:
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

## Quality gate before commit

```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run flake8 . && \
uv run mypy . && \
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
```

Do not commit if this fails. Fix the code properly.

## Paid/credentialed checks

These may hit paid LLM APIs and require keys. Ask before running if credentials/cost are not explicitly approved.

```bash
uv run pytest tests/e2e/ --alluredir=allure-results -v
uv run python -m benchmarks run
```

## Architecture map

- cast/: Director and performer agents
- engine/: public GameEngine API and factory
- models/: domain models
- knowledge/: scoped knowledge graph
- timeline/: game clock and scheduled events
- llm/: provider abstraction
- prompts/: composable prompt templates
- db/: persistence and ORM/domain converters
- interfaces/: web UI and admin
- benchmarks/: narration-quality benchmark harness

## Development rules

- Never push directly to main unless Max explicitly says “push to main”.
- Use a feature branch for every code change.
- Keep changes surgical and minimal.
- Do not add speculative abstractions.
- Do not silently change lint/type/test configuration.
- Do not add noqa, type-ignore, pragma, or config suppressions to bypass quality rules.
- For bug fixes: write the regression test first, run it and observe the expected failure, then fix the root cause.
- Prefer tests at the consumer-side integration seam. Prove that the consumer receives the value, not only that the supplier produces it.
- Maintain 90%+ unit test coverage.

## PR expectations

Every PR should include:
- summary
- linked issue/card if applicable
- test evidence
- screenshots or notes for web UI changes
- benchmark/e2e evidence for narrative-quality changes, if approved

## Release safety

Agents may prepare release artifacts but may not publish a public release without Max approval.

Before a release, follow docs/studio/03-release-checklist.md.

## Existing guidance

CLAUDE.md contains detailed repo guidance and remains authoritative for coding conventions. If AGENTS.md and CLAUDE.md conflict, stop and ask Max before proceeding.
