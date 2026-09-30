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

- Trunk development: `main` is the only long-lived development branch. Use short-lived branches for code changes and open GitHub PRs early; PR review is the default code-review surface.
- For non-trivial features, use Spec Kit as the repo-tracked requirements/planning layer before coding when it helps clarify scope: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` for medium work; add `/speckit-clarify` (blocking unknowns only) and one `/speckit-analyze` pass for large/risky work; `/speckit-checklist` and `/speckit-converge` are opt-in. See `docs/decisions/0017-adopt-spec-kit-as-requirements-layer.md`, `docs/studio/13-spec-driven-development.md`, and `.specify/memory/constitution.md`.
- `/speckit-implement` is optional, not the default autopilot. Spec Kit review steps fix only blocking contradictions: one remediation pass, then escalate to Max; never grow scope while fixing findings (constitution Principle VI). Implementation still follows CLAUDE.md, accepted ADRs, deterministic verification, and PR review.
- Agents may create branches, push them, and open PRs for code work without asking first. Direct pushes to `main` still require Max to explicitly say “push to main”.
- Agents may merge low-risk PRs after required deterministic checks and CI pass. Stop and ask before merging product/release behavior changes, destructive data changes, paid/e2e/benchmark-dependent changes, or anything with unclear risk.
- Release tags are the release boundary: cut annotated tags from `main` only after Max approval and the release checklist.
- See `docs/decisions/0014-trunk-development-with-release-tags.md` for the accepted workflow decision.
- Keep changes surgical and minimal.
- Do not add speculative abstractions.
- Do not silently change lint/type/test configuration.
- Do not add noqa, type-ignore, pragma, or config suppressions to bypass quality rules.
- For bug fixes: write the regression test first, run it and observe the expected failure, then fix the root cause.
- Prefer tests at the consumer-side integration seam. Prove that the consumer receives the value, not only that the supplier produces it.
- Maintain 90%+ unit test coverage.

## Kanban workers: prefer Claude Code print mode

When running as a Hermes Kanban worker on Storyteller coding, debugging, refactoring, or review tasks, prefer delegating non-trivial inner-loop work to Claude Code print mode (`claude -p`). Hermes remains responsible for task scoping, final diff inspection, verification, and Kanban handoff.

Recommended implementation pattern:

```bash
claude -p "
You are working inside Storyteller.

Task:
<task body>

Rules:
- Follow AGENTS.md and CLAUDE.md.
- Keep changes surgical and minimal.
- For bug fixes, write or adjust the regression test first and observe it fail before fixing.
- You may push a short-lived branch and open a PR when the implementation is verified.
- Do not run paid/e2e/benchmark checks unless Max explicitly approved them.
- After editing, report changed files and commands run.
" \
  --allowedTools "Read,Edit,Write,Bash(git diff*),Bash(uv run pytest*),Bash(uv run ruff*),Bash(uv run mypy*),Bash(uv run flake8*)" \
  --max-turns 25 \
  --output-format json
```

Recommended review pattern:

```bash
git diff main...HEAD | claude -p "
Review this Storyteller diff. Focus on bugs, missed tests, prompt/agent regressions, async issues, DB/converter risks, and overengineering. Return blocking findings first, then non-blocking notes.
" \
  --allowedTools "Read" \
  --max-turns 3
```

Guardrails:
- Do not use `--dangerously-skip-permissions` by default; prefer scoped `--allowedTools`.
- Do not trust Claude output blindly: inspect changed files and run relevant verification before completing or blocking the Kanban card.
- If `claude -p` fails because of auth, rate limits, or tool permissions, continue with Hermes tools and mention the failure in the handoff.

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
