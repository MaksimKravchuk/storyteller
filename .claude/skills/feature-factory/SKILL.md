---
name: feature-factory
description: Default workflow in this repo. Runs the upstream Researcher → Story Writer → Spec Writer → parallel QA review (qa-tester + agent-qa-tester) chain with three human approval gates before any code is written. Use ONLY when the user explicitly invokes /feature-factory, types "feature-factory" or "factory <idea>", or asks to start the factory workflow. Do NOT auto-trigger on phrases like "build a feature" or "design a feature" — those are too generic; require explicit "feature-factory" / "factory" in the user's message. Once invoked, the chain covers any change touching cast/, engine/, prompts/, db/, knowledge/, timeline/, models/, interfaces/, or research/. Skip only for typos, comment fixes, docs-only edits, test-only changes following an obvious pattern, and recently-introduced-regression reverts. When in doubt, run the chain.
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

Six steps, three pauses, then the existing PR-time gates.

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

This is the first of four approval gates in the chain.

### Step 3 — Spec Writer  →  PAUSE for human approval

Invoke the `spec-writer` agent via the Agent tool with:
- The approved story.
- The Researcher's brief.
- `CLAUDE.md` (project conventions).

The agent returns a technical brief covering: files that will change, domain model changes (with `db/converters.py` round-trip), agent/prompt changes, the prompt-variable contract table (EN+RU), tests required (consumer-seam first), knowledge/timeline/async hooks, risks, decision-records decision, and open questions.

**Stop and present the brief to the human.** Wait for explicit approval before invoking the QA review. If the human amends the brief, capture the amended version — the QA agents read the *approved* brief.

If the brief flags a new significant decision in architecture / agent roles / prompt boundaries / persistence / release / player-facing behaviour, **do not write the decision record yet** — the brief notes the need, and the main session runs `/decision-records` between the QA test-plan approval and `gh pr create`.

This is the second of four approval gates.

### Step 4 — QA review  →  PAUSE for human approval

Invoke **both** QA agents **in parallel** (single message, two `Agent` tool calls) with:
- The approved spec-writer brief.
- The Researcher's brief.
- `CLAUDE.md`.

The two agents:
- `qa-tester` (deterministic) — owns tool-call shape correctness, schema/model invariants & DB round-trip, validation/error paths, deterministic graph/clock behavior, locale parity, async/concurrency correctness.
- `agent-qa-tester` (AI/agent) — owns semantic determinism / tool-selection stability, tool-selection appropriateness, prompt-injection robustness, narrative/persona consistency, LLM-as-judge wiring in benchmark scenarios, regression-budget hand-off to the benchmark suite.

Each returns a **Mode A — QA test plan**: failure-class checklist, recommended test scaffolds (names + fixture sketches + assertion shape, no Python), and explicit hand-offs to peer tools and to the sibling agent. The two plans are designed to be non-overlapping; if you see double coverage, ask one to defer to the other.

**Stop and present both plans to the human side-by-side.** Wait for explicit approval (or amendments) before any code is written. The implementer treats the approved plans as the test contract — every scaffold lands as a test in the same PR as the code.

This is the third of four approval gates.

### Step 5 — Build (main session)

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
- Before `gh pr create`, invoke `qa-tester` and `agent-qa-tester` again **in parallel** in **Mode B (gap analysis)** against the unstaged/local diff. Each returns a regression-coverage gap report with a verdict (`clean | needs-attention | blocking`). `blocking` must be resolved before opening the PR; `needs-attention` is presented to the human for a ship/fix decision.

### Step 6 — PR  →  human approval gate #4

Open the PR via `gh pr create`. This triggers the existing PR-time hook chain:

1. `require-skill simplify` — `/simplify` reviews staged changes for reuse, quality, and efficiency.
2. `require-skill pr-review-toolkit_review-pr` — multi-agent PR review (code-reviewer, code-simplifier, silent-failure-hunter, pr-test-analyzer, type-design-analyzer, comment-analyzer).
3. `require-skill decision-records` — confirms accepted constraints are preserved or a new record is in place if a significant decision is being made.
4. `require-prompt-audit.sh` — `prompt-wiring-auditor` checks that every new `required_vars` reaches the consumer's `.render()` call site, in both locales.

The human reviews and merges the PR on GitHub — the fourth approval gate.

## Composing with `decision-records`

The `decision-records` skill owns the format and lifecycle of durable architectural records. This skill defers to it:

- The Researcher *consults* records (read-only).
- The Spec Writer *flags* whether a record is needed (no record content in the brief).
- The main session *invokes* `/decision-records` between QA test-plan approval and PR open if the flag was raised.
- The PR-time `require-skill decision-records` hook *enforces* the consult/create at merge time.

Do not duplicate decision-record content in the brief.

## Failure modes & how to recover

- **The Researcher missed something.** The brief will reference an N/A section that turns out to matter. Restart the chain at step 1 with the gap noted; do not paper over it in the brief.
- **The story-writer guessed a business rule.** That's a bug in the story-writer prompt — capture the case and tighten the story-writer agent file. Re-run step 2 with the rule under "open questions" instead.
- **The spec-writer skipped the prompt-variable contract table.** Re-run step 3; the `prompt-wiring-auditor` exists *only* to catch this, and you don't want to find out at PR time.
- **The builder discovers the brief was wrong.** Stop building. Surface the mismatch as feedback. Either restart at step 3 with the new constraint or amend the story (step 2) if the constraint changes the user-observable behavior.
- **A QA agent's Mode B report returns `blocking`.** Do not open the PR. Resolve the missing tests/scenarios first. If the gap reflects a spec gap (the brief was silent on a behavior the agent rightly wants covered), amend the brief and re-run Step 4 — do not paper over it with a one-off test.

## Trivial-edit exception (skip the chain)

The chain has cost. For changes whose blast radius is genuinely contained — typos, comment fixes, docs-only edits, isolated test additions following an obvious pattern, and recently-introduced-regression reverts — skip the chain and edit directly. The existing PR-time gates still apply.

If the change touches a `PromptSection` or `required_vars`, it is **not** trivial regardless of line count. Run the chain.
