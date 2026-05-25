---
name: feature-factory
description: Default workflow for any non-trivial change in this repo. Runs the upstream Researcher → Story Writer → Spec Writer chain with two human approval gates before any code is written. Use when starting work on a new feature, bug fix that touches behavior, or any change to cast/, engine/, prompts/, db/, knowledge/, timeline/, models/, interfaces/, or research/. Triggered by /feature-factory, "build feature", "design feature", "factory <idea>", or whenever you're about to start non-trivial implementation work. Skip only for typos, comment fixes, docs-only edits, test-only changes following an obvious pattern, and recently-introduced-regression reverts. When in doubt, run the chain.
context: fork
allowed-tools: Read, Grep, Glob, Bash, Agent
---

# Feature factory — the default workflow

For any non-trivial change in this repo, run this chain **before** writing code. The chain protects against the failure classes documented in `CLAUDE.md` (prompt-variable silent drops, locale skew, domain↔ORM mismatch, scope-filtered knowledge graph blind spots) by forcing deliberate research and design upstream of implementation — where the cost of fixing a mistake is one paragraph rewrite, not ten patched files.

## When to use this skill

Use this skill when:

- Starting work on a new feature, however small.
- Making a behavior change that touches `cast/`, `engine/`, `prompts/`, `db/`, `knowledge/`, `timeline/`, `models/`, `interfaces/`, or `research/`.
- Fixing a bug whose root cause is unclear, or whose fix changes a contract.
- About to edit a `PromptSection` or its `required_vars`.
- About to add or change a field on a domain model in `models/`.
- Touching the producer or consumer of any prompt variable.

Do **not** use this skill for:

- Typo and comment fixes.
- README/docs-only edits with no behavior change.
- Test-only additions that follow an obvious existing pattern.
- Reverting a regression introduced in the last few commits (use the original review trail instead).

When in doubt, run the chain. The cost is one Researcher pass and a story you can approve in 30 seconds.

## The chain

Five steps, two pauses, then the existing PR-time gates.

### Step 1 — Researcher

Invoke the `codebase-researcher` agent via the Agent tool with:
- The caller's rough feature description.
- Any scope hints the caller volunteered.

The agent returns a research brief covering: relevant files (`file:line`), producer→consumer chains, locale parity audit (EN+RU), the six storyteller-specific risk classes, similar features, and any accepted decision records on the touched surface.

**Do not skip this step.** The story-writer and spec-writer both depend on the brief.

### Step 2 — Story Writer  →  PAUSE for human approval

Invoke the `story-writer` agent via the Agent tool with:
- The caller's feature description.
- The Researcher's brief.

The agent returns a user story with acceptance criteria, edge cases, out-of-scope, and open questions.

**Stop and present the story to the human.** Wait for explicit approval before invoking the spec-writer. If the human amends the story, capture the amended version — the spec-writer reads the *approved* story, not the draft.

This is the first of three approval gates in the chain.

### Step 3 — Spec Writer  →  PAUSE for human approval

Invoke the `spec-writer` agent via the Agent tool with:
- The approved story.
- The Researcher's brief.
- `CLAUDE.md` (project conventions).

The agent returns a technical brief covering: files that will change, domain model changes (with `db/converters.py` round-trip), agent/prompt changes, the prompt-variable contract table (EN+RU), tests required (consumer-seam first), knowledge/timeline/async hooks, risks, decision-records decision, and open questions.

**Stop and present the brief to the human.** Wait for explicit approval before any code is written.

If the brief flags a new significant decision in architecture / agent roles / prompt boundaries / persistence / release / player-facing behaviour, **do not write the decision record yet** — the brief notes the need, and the main session runs `/decision-records` between the brief approval and `gh pr create`.

This is the second of three approval gates.

### Step 4 — Build (main session)

The main session implements the approved brief. Discipline (per `CLAUDE.md`):

- Match existing patterns named by the Researcher.
- Add the consumer-seam tests the brief specifies, alongside the code.
- For prompt changes, update both EN and RU locales — the brief's contract table is the spec.
- For domain-model changes, round-trip through `db/converters.py`.
- Run the gauntlet before commit:
  ```bash
  uv run ruff check . && uv run ruff format --check . && uv run flake8 . && uv run mypy . && uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
  ```
- If the gauntlet fails, **refactor** — do not commit with failures and do not bypass hooks.
- If the brief flagged a new significant decision, invoke `/decision-records` before `gh pr create`.

### Step 5 — PR  →  human approval gate #3

Open the PR via `gh pr create`. This triggers the existing PR-time hook chain:

1. `require-skill simplify` — `/simplify` reviews staged changes for reuse, quality, and efficiency.
2. `require-skill pr-review-toolkit_review-pr` — multi-agent PR review (code-reviewer, code-simplifier, silent-failure-hunter, pr-test-analyzer, type-design-analyzer, comment-analyzer).
3. `require-skill decision-records` — confirms accepted constraints are preserved or a new record is in place if a significant decision is being made.
4. `require-prompt-audit.sh` — `prompt-wiring-auditor` checks that every new `required_vars` reaches the consumer's `.render()` call site, in both locales.

The human reviews and merges the PR on GitHub — the third approval gate.

## Composing with `decision-records`

The `decision-records` skill owns the format and lifecycle of durable architectural records. This skill defers to it:

- The Researcher *consults* records (read-only).
- The Spec Writer *flags* whether a record is needed (no record content in the brief).
- The main session *invokes* `/decision-records` between brief approval and PR open if the flag was raised.
- The PR-time `require-skill decision-records` hook *enforces* the consult/create at merge time.

Do not duplicate decision-record content in the brief.

## Failure modes & how to recover

- **The Researcher missed something.** The brief will reference an N/A section that turns out to matter. Restart the chain at step 1 with the gap noted; do not paper over it in the brief.
- **The story-writer guessed a business rule.** That's a bug in the story-writer prompt — capture the case and tighten the story-writer agent file. Re-run step 2 with the rule under "open questions" instead.
- **The spec-writer skipped the prompt-variable contract table.** Re-run step 3; the `prompt-wiring-auditor` exists *only* to catch this, and you don't want to find out at PR time.
- **The builder discovers the brief was wrong.** Stop building. Surface the mismatch as feedback. Either restart at step 3 with the new constraint or amend the story (step 2) if the constraint changes the user-observable behavior.

## Trivial-edit exception (skip the chain)

The chain has cost. For changes whose blast radius is genuinely contained — typos, comment fixes, docs-only edits, isolated test additions following an obvious pattern, and recently-introduced-regression reverts — skip the chain and edit directly. The existing PR-time gates still apply.

If the change touches a `PromptSection` or `required_vars`, it is **not** trivial regardless of line count. Run the chain.
