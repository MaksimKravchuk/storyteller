---
name: decision-records
description: Create or update ADR-style decision records for durable Storyteller product, architecture, agent, prompt, persistence, evaluation, or release decisions. Use when asked to preserve why a decision was made, when changing important boundaries, or before changing a system that may already have documented rationale.
context: fork
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Preserve decision history with ADRs

Storyteller decision history belongs in repo-tracked decision records, not only in chat history, PR descriptions, or personal memory. Use this skill to capture **what was decided, why, what alternatives were rejected, consequences, verification, and future-agent guardrails**.

## When to use this skill

Use this skill when:

- The user asks to remember why a Storyteller decision was made.
- You add or change an architectural boundary, agent role, prompt responsibility, persistence behavior, evaluation policy, release strategy, or major product direction.
- You are about to change architecture, prompt boundaries, agent roles, persistence, release strategy, or player-facing behavior and need to check existing rationale first.
- A PR or implementation implies a durable design/product decision that future agents may otherwise reverse.
- You need to reconstruct a past decision from repo artifacts, docs, issues, PRs, or user-provided context.

Do **not** use this skill for:

- Temporary task status.
- PR numbers, commit SHAs, or changelog entries.
- Tiny implementation details with no long-term design impact.
- Facts better captured in inline comments, README, tests, or `CLAUDE.md` rules.

## Storage location

Use the existing repo convention for the decision type:

- **Founder/product/release decisions** live in `docs/studio/09-founder-decision-register.md`. They use the existing `Chosen | Defaulted | Max decision required | Deferred` status vocabulary and `D00N` numbering.
- **Architecture or implementation decisions** may live in `docs/decisions/` when they need a standalone record. They use the ADR status vocabulary `Proposed | Accepted | Superseded | Rejected` and `0001-…` numbering.

Do not mix the vocabularies (e.g. do not mark a founder register entry as `Accepted`, and do not mark a `docs/decisions/` ADR as `Max decision required`).

For standalone ADRs, use this filename format:

```text
docs/decisions/0001-use-theater-style-agent-architecture.md
docs/decisions/0002-add-dedicated-narrator-agent.md
docs/decisions/0003-separate-director-from-performer-agents.md
```

Use the next unused number. Keep titles short, lowercase, and descriptive.

## Required workflow

### 1. Search before writing

Before creating a new record, check for existing decision history:

```bash
find . -type f \( -iname '*decision*' -o -iname '*adr*' \)
grep -RE "ADR-|## Decision|docs/decisions|Founder Decision Register" -n docs CLAUDE.md AGENTS.md .claude 2>/dev/null || true
```

For founder/product/release decisions, update `docs/studio/09-founder-decision-register.md` unless the decision needs a standalone ADR. If a relevant ADR or register entry exists, update it or mark it superseded instead of creating a duplicate.

### 2. Gather evidence

Inspect relevant files and tests before writing. Ground the ADR in artifacts:

- code paths being changed
- prompt templates
- tests or benchmark harnesses
- existing docs
- linked issues/PRs if provided by the user
- user-provided rationale from the current conversation

If reconstructing a past decision and evidence is incomplete, label uncertain points as **Inferred** or **Open question**. Do not invent historical rationale.

### 3. Classify the decision

Name the kind of decision so future agents understand the scope:

- **Architecture:** module boundaries, services, data flow, orchestration.
- **Product:** release target, UX direction, non-goals, beta strategy.
- **Agent/prompt:** performer roles, prompt boundaries, evaluation rules.
- **Operations:** deployment, CI, secrets, release gates.
- **Persistence:** database, migrations, domain/ORM boundaries.

### 4. Write or update the ADR

Use this template unless the repo already has a different ADR template:

```md
# ADR-000N: Short imperative title

Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded | Rejected
Decision owner: <person/team, optional — agents are not valid sole owners for product, release, audience, spend, or privacy decisions; those belong to Max>
Related: <issues, PRs, files, prior ADRs>

## Context

What problem or pressure led to this decision?
What was happening before this choice?
What constraints mattered?

## Decision

What did we choose?
Be direct and specific.

## Rationale

Why is this the right choice for Storyteller now?
Explain product, engineering, operational, narrative-quality, or UX importance.

## Alternatives considered

### Alternative 1: <name>

Why it was considered.
Why it was not chosen.

### Alternative 2: <name>

Why it was considered.
Why it was not chosen.

## Consequences

Positive consequences:
- ...

Tradeoffs / risks:
- ...

What future agents must preserve:
- ...

## Verification / tests

How do we know the decision is implemented or preserved?
List tests, review checks, benchmark evidence, smoke tests, or files to inspect.

## Related files

- `path/to/file.py`
- `path/to/prompt.md`
- `tests/path/test_file.py`
```

### 5. Connect future-agent guardrails

If the decision must constrain future work, make that explicit in the ADR under:

```md
What future agents must preserve:
- ...
```

If there is no general pointer yet, add or keep a short `CLAUDE.md`/`AGENTS.md` rule telling agents to inspect both `docs/decisions/` and `docs/studio/09-founder-decision-register.md` before changing architecture, agent roles, prompt boundaries, persistence, release strategy, or player-facing behavior.

## Good rationale pattern

A good rationale answers:

- What problem did the old design create?
- Why does this matter to players, maintainers, or release safety?
- Why is this better than the obvious alternative?
- What boundary should future agents not collapse?
- What tests or review checks protect it?

Example:

```md
We added a dedicated Narrator because player-facing prose quality is a separate concern from game-state orchestration. The Director should decide what happens and coordinate performers; the Narrator should turn scene state, NPC actions, memory, and tone into coherent player-facing text.

This matters because Storyteller's differentiator is not merely simulating quest state, but producing compelling interactive fiction. Keeping Narrator separate lets us improve prose quality, continuity, tone, and benchmark evaluation without overloading Director prompts or mixing orchestration with presentation.
```

## Common pitfalls

1. **Documenting only the outcome**
   - Bad: "We added Narrator."
   - Good: "We added Narrator because Director orchestration and player-facing prose quality are separate responsibilities."

2. **Omitting rejected alternatives**
   - Future agents need to know why not to revert to the simpler or more obvious design.

3. **Writing task progress as a decision**
   - "PR merged" is not a decision record. "We chose FastAPI for the web UI because..." can be.

4. **Inventing history**
   - If the repo does not prove the rationale and the user did not provide it, label it as inferred or ask.

5. **Creating duplicates**
   - Search first. Update, supersede, or cross-reference existing ADRs.

6. **Making the ADR too abstract**
   - Include related files and verification checks so future agents can act on it.

## Verification checklist

Before finishing:

- [ ] Existing decision records were searched first.
- [ ] The ADR captures context, decision, rationale, alternatives, consequences, verification, and related files.
- [ ] Status and date are set.
- [ ] Filename numbering does not collide.
- [ ] Future-agent guardrails are explicit.
- [ ] Uncertain historical reconstruction is labeled rather than invented.
- [ ] `CLAUDE.md` or `AGENTS.md` points agents to decision records when the decision class is important.
