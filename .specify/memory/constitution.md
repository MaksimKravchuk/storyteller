# Storyteller Constitution

## Core Principles

### I. Player-Visible Value First

Every specification MUST describe the player, founder, operator, or maintainer value before implementation details. Feature specs focus on what changes for users and why it matters; technology choices belong in the implementation plan. Narrative-quality work MUST define how the player experience improves and how regressions will be detected.

### II. Surgical, Test-First Delivery

Changes MUST be minimal and scoped to the requested outcome. Bug fixes require a regression test that fails for the original behavior before implementation. New behavior requires independently testable user stories and acceptance scenarios. Do not introduce speculative abstractions, broad rewrites, lint/type/test suppressions, or unrelated cleanup.

### III. Consumer-Seam Verification

Contracts are proven at the boundary where the consumer receives the value, not only where the supplier produces it. Prompt, agent, schema, and persistence changes MUST include tests or review evidence that downstream consumers actually receive and use the new data or behavior. For paired locale prompts, update and verify both locale variants unless the spec explicitly scopes one locale.

### IV. Narrative Safety and Benchmark Evidence

Changes touching `cast/`, `prompts/`, narrative-affecting `engine/` paths, benchmark scenarios, or player-facing prose MUST define deterministic verification. Paid e2e and benchmark runs remain opt-in and require explicit approval, but the plan MUST say what evidence is required before merge or release. Safety, moderation, and player-facing behavior changes MUST preserve accepted decision records unless superseded by a new ADR.

### V. Repo-Tracked Decisions and PR Evidence

Significant architecture, agent-role, prompt-boundary, persistence, release, or player-facing decisions MUST create or update an ADR under `docs/decisions/`. Each PR MUST include a summary, linked spec or task context when available, deterministic test evidence, and screenshots or benchmark/e2e notes when relevant. Trunk development uses short-lived branches and PRs; direct pushes to `main` require explicit Max approval.

## Storyteller Constraints

- Python 3.11+, async-first architecture.
- Use `uv` for project commands.
- Keep the theater-style multi-agent architecture: Director coordinates specialized performer agents rather than collapsing responsibilities without an accepted ADR.
- Respect existing ownership boundaries:
  - `cast/`: performer agents and orchestration.
  - `engine/`: public GameEngine API and factory.
  - `prompts/`: composable prompt templates.
  - `db/`: persistence and ORM/domain converters.
  - `interfaces/`: web UI and admin surfaces.
  - `benchmarks/`: deterministic narration-quality harness.
- Paid or credentialed checks (`tests/e2e/`, `benchmarks run`) require explicit approval.
- Release tags are the release boundary; preparing release artifacts is allowed, publishing release tags requires Max approval.

## Spec-Driven Workflow

For non-trivial work, use the Spec Kit flow as a requirements and planning layer:

```text
/speckit-specify -> /speckit-clarify -> /speckit-plan -> /speckit-checklist -> /speckit-tasks -> /speckit-analyze
```

Implementation remains governed by `CLAUDE.md`, `AGENTS.md`, accepted ADRs, and PR review. `/speckit-implement` is optional, not the default. Prefer the existing Hermes/Claude PR workflow for implementation: scope from the spec, code surgically, verify, inspect the diff, push a short-lived branch, and open a PR.

## Quality Gates

Before implementation starts, plans MUST state:

- which existing ADRs or founder-decision-register entries were inspected;
- whether a new ADR is required;
- which tests or deterministic checks prove the change;
- whether paid/e2e/benchmark evidence is required and whether approval was granted;
- what demo or PR evidence is expected for the touched surface.

Before merge, deterministic local checks should pass unless the PR is docs-only or explicitly scoped otherwise:

```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run flake8 . && \
uv run mypy . && \
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
```

Docs-only changes may use targeted Markdown/file inspection plus PR review evidence instead of the full Python gauntlet.

## Governance

This constitution applies to Spec Kit artifacts and complements `CLAUDE.md`, `AGENTS.md`, and accepted ADRs. If it conflicts with a more specific accepted ADR or explicit instruction from Max, stop and surface the conflict. Amendments require a PR and, when the change affects architecture, agent roles, prompt boundaries, persistence, release strategy, or player-facing behavior, a decision record.

**Version**: 1.0.0 | **Ratified**: 2026-06-30 | **Last Amended**: 2026-06-30
