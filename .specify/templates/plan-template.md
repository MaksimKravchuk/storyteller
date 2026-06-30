# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+

**Primary Dependencies**: FastAPI/aiohttp interfaces, async SQLAlchemy/asyncpg persistence, NetworkX knowledge graph, provider-agnostic LLM clients, pytest tooling (adjust if feature does not touch these)

**Storage**: PostgreSQL via async SQLAlchemy when persistence is needed; in-memory/domain models for engine flows; files for docs/spec artifacts

**Testing**: pytest + pytest-asyncio; ruff, ruff format --check, flake8, mypy; optional paid e2e/benchmarks only with approval

**Target Platform**: Linux server/local development via uv; web UI/admin where applicable

**Project Type**: AI-powered text quest engine with FastAPI web UI, admin dashboard, async engine, and theater-style multi-agent architecture

**Performance Goals**: [domain-specific, e.g., preserve existing turn latency, avoid extra LLM calls, maintain benchmark score, or NEEDS CLARIFICATION]

**Constraints**: Surgical changes, no speculative abstractions, no lint/type/test suppressions, consumer-seam tests, prompt locale parity where applicable, no paid checks without approval

**Scale/Scope**: [feature-specific scope; include affected modules and whether this is player-facing, admin-only, or internal]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Player-visible value first**: [How the spec describes user/founder/operator value]
- **Surgical, test-first delivery**: [Regression/new-behavior test strategy]
- **Consumer-seam verification**: [Where the downstream consumer receives the value]
- **Narrative safety and benchmark evidence**: [Narrative/prompt impact and required evidence]
- **Repo-tracked decisions and PR evidence**: [ADRs/founder decisions inspected; whether new ADR is required]
- **Paid checks**: [No / e2e / benchmarks / both; approval status]

If any gate cannot pass, document the violation in Complexity Tracking before proceeding.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# Select the touched areas for this feature and delete the rest from generated plans.
cast/                 # Director and performer agents
engine/               # public GameEngine API and factory
models/               # domain models
knowledge/            # scoped knowledge graph
timeline/             # game clock and scheduled events
llm/                  # provider abstraction
prompts/              # prompt templates; keep locale parity when applicable
db/                   # persistence, Alembic, ORM/domain converters
interfaces/           # web UI and admin
benchmarks/           # narration-quality scenarios and scoring
tests/                # pytest suites; prefer consumer-seam integration tests
```

**Structure Decision**: [List the exact directories/files this feature will touch and why]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
