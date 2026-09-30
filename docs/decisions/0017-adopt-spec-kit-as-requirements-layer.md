# ADR-0017: Adopt Spec Kit as Storyteller's Requirements Layer

Date: 2026-06-30
Status: Accepted
Decision owner: Max / Hermes
Related: `docs/studio/13-spec-driven-development.md`, `.specify/memory/constitution.md`, `CLAUDE.md`, `AGENTS.md`

## Context

Storyteller already has strong implementation guardrails: trunk development with short-lived PRs, deterministic local checks, ADRs for significant decisions, benchmark evidence for narrative-impacting changes, and Claude/Hermes review workflows.

The weak point was earlier in the lifecycle. Voice notes, chat discussions, and agent prompts could contain enough intent for one implementation session, but not always enough durable structure for future agents. That makes it easy for later work to lose the original user story, acceptance criteria, rationale, benchmark expectations, or clarification history.

GitHub Spec Kit provides a spec-driven workflow that records requirements, clarification, plans, checklists, and tasks before implementation. It supports Claude Code via generated skills and keeps artifacts in the repository.

## Decision

Adopt GitHub Spec Kit as Storyteller's repo-tracked requirements and planning layer for non-trivial feature work.

Spec Kit artifacts live under `.specify/`, generated Claude skills live under `.claude/skills/speckit-*`, and project-specific rules live in `.specify/memory/constitution.md`.

The default Storyteller flow is:

```text
/speckit-specify -> /speckit-clarify -> /speckit-plan -> /speckit-checklist -> /speckit-tasks -> /speckit-analyze
```

Implementation still follows the existing Storyteller workflow: Hermes scopes and verifies, Claude Code may write code, deterministic checks must pass, significant decisions require ADRs, and PRs remain the review surface.

`/speckit-implement` is optional and is not the default autopilot for Storyteller.

## Rationale

Spec Kit gives future agents a durable source of truth for what a feature is meant to achieve before code exists. This is especially valuable for Storyteller because gameplay, prompt, agent, and benchmark changes often have product intent that is not obvious from code diffs alone.

Keeping Spec Kit as the requirements layer avoids replacing existing controls that already work well:

- ADRs remain authoritative for architecture and product decisions.
- `CLAUDE.md` and `AGENTS.md` remain authoritative for implementation behavior.
- PRs remain the integration and review boundary.
- Benchmarks and e2e checks remain opt-in when they cost money or require credentials.

This separation lets Storyteller benefit from spec-driven development without giving a generic generated workflow permission to bypass project-specific safety gates.

## Alternatives considered

### Alternative 1: Continue with chat-only task intake

Chat-only intake is fast but loses structured acceptance criteria, clarification history, and planned verification. It relies on session search and memory reconstruction instead of repo-tracked artifacts. This was rejected because Storyteller has many long-lived product and architecture decisions that future agents need to inspect without replaying chat history.

### Alternative 2: Use Spec Kit as the full implementation engine by default

Spec Kit includes `/speckit-implement`, but using it as the default implementation runner would overlap with Storyteller's existing Claude/Hermes PR workflow and could encourage broad, generic implementation behavior. This was rejected because Storyteller needs surgical changes, consumer-seam tests, ADR inspection, prompt locale parity, and explicit paid-check approvals.

### Alternative 3: Write a custom Storyteller-only spec workflow

A custom workflow could be more tailored, but it would require maintaining command templates, scripts, and agent integration ourselves. This was rejected for now because Spec Kit provides a maintained baseline, and Storyteller-specific behavior can be captured in the constitution and documentation.

## Consequences

Positive consequences:

- Non-trivial features can carry durable `spec.md`, `plan.md`, `tasks.md`, and checklist artifacts.
- Future agents can inspect planned user value and acceptance criteria before changing code.
- PR bodies can link to specs and task files for better review context.
- Clarifications and evidence expectations are recorded before implementation starts.

Tradeoffs / risks:

- More documentation overhead for small changes.
- Generated Spec Kit skills and templates may change across upgrades and need review.
- If agents treat `/speckit-implement` as default autopilot, they may bypass Storyteller-specific guardrails.
- `.claude/` can sometimes contain local/private agent state; only generated project skills should be committed.

What future agents must preserve:

- Treat Spec Kit as intake/planning, not as a replacement for Storyteller PR, ADR, and verification gates.
- Use ADRs for significant architecture, agent-role, prompt-boundary, persistence, release, or player-facing decisions.
- Do not run paid e2e/benchmark checks without approval.
- Keep the constitution aligned with `CLAUDE.md`, `AGENTS.md`, and accepted ADRs.

## Verification / tests

This is a docs/workflow decision. Verification is by file inspection and PR review:

- `.specify/memory/constitution.md` exists and contains Storyteller-specific principles.
- `.claude/skills/speckit-*` exist from `specify init --integration claude`.
- `docs/studio/13-spec-driven-development.md` explains usage and guardrails.
- `CLAUDE.md` and `AGENTS.md` point future agents to the Spec Kit workflow.

No app tests, e2e tests, or benchmarks are required for this docs-only adoption.

## Related files

- `.specify/memory/constitution.md`
- `.specify/templates/spec-template.md`
- `.specify/templates/plan-template.md`
- `.claude/skills/speckit-specify/SKILL.md`
- `.claude/skills/speckit-plan/SKILL.md`
- `.claude/skills/speckit-tasks/SKILL.md`
- `docs/studio/13-spec-driven-development.md`
- `CLAUDE.md`
- `AGENTS.md`
