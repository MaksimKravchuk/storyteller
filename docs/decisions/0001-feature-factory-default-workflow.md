# ADR-0001: Feature-factory chain is the default workflow for non-trivial changes

Date: 2026-05-25
Status: Accepted; PR/merge autonomy superseded in part by ADR-0014
Decision owner: Max
Related: [feat/feature-factory branch], [@sairahul1 "Software Factory" article](https://x.com/sairahul1/status/2058832033628241931), `docs/studio/09-founder-decision-register.md`

## Context

Storyteller has invested heavily in **downstream** quality gates: the pr-review-toolkit chain (code-reviewer, code-simplifier, silent-failure-hunter, pr-test-analyzer, type-design-analyzer, comment-analyzer), the project-local `prompt-wiring-auditor` agent (which exists *only* to catch the silent-drop failure class documented in CLAUDE.md), the brand-new `decision-records` skill + hook, plus four PreToolUse hooks gating `git commit` / `gh pr create` / `git push`.

The **upstream** side — research, story shaping, and technical design before any code is written — was un-systematized. Every feature relied on the main Claude Code session to play all four roles (researcher, story writer, designer, builder) at once, in one mixed context. The documented past regression — NPC alias data well-tested on `NPCCard.known_names_for_player` but never reaching the Narrator's prompt body — lived in exactly this gap: producer well-tested, consumer wiring un-tested, no upstream pass that would have surfaced the contract.

@sairahul1's "Software Factory" article (linked above) prescribes a 7-agent chain with three human approval gates. The downstream four roles of that chain already exist here (and arguably better, given the storyteller-specific `prompt-wiring-auditor`). The upstream three — Researcher, Story Writer, Spec Writer — were genuinely missing.

## Decision

Adopt the **upstream half** of the article's chain as the default workflow for any non-trivial change in this repo, surfaced as a `/feature-factory` skill that runs three new read-only subagents in sequence:

1. `codebase-researcher` — maps the touched surface, audits the six storyteller failure classes, lists relevant accepted decision records.
2. `story-writer` — produces a user story with acceptance criteria. **Human approval gate #1.**
3. `spec-writer` — produces a technical brief with an explicit producer→consumer prompt-variable contract (EN+RU), `db/converters.py` round-trip, consumer-seam tests, and a decision-records pointer. **Human approval gate #2.**

After brief approval, the main session implements the brief, runs the gauntlet, optionally invokes `/decision-records`, and opens the PR — which triggers the existing four PR-time gates (simplify, pr-review-toolkit:review-pr, decision-records, prompt-audit). The GitHub PR review is **human approval gate #3.**

`CLAUDE.md` declares the chain the default and names the trivial-edit exception (typos, comment fixes, README/docs-only edits, isolated test additions, recently-introduced-regression reverts). If a change touches a `PromptSection` or `required_vars`, it is *not* trivial regardless of line count.

## Rationale

- **Catch contract mistakes before they spread across 10 files.** The article's framing — "wrong assumptions in the plan become wrong database models, become wrong APIs, become wrong UIs" — is exactly the failure mode `prompt-wiring-auditor` was built to detect after the fact. The Spec Writer's mandatory prompt-variable-contract table catches the same class *before* code is written, in both EN and RU locales.
- **Compose, don't duplicate.** The Spec Writer points at the existing `decision-records` skill rather than embedding decision-record content. Records capture durable constraints; the brief is per-feature.
- **Match the repo's reality.** Article prescribes Backend Builder + Frontend Builder + Test Verifier + Validator as separate agents. Skipped here: this repo is Python-first (no React surface for a frontend builder), already mandates consumer-seam tests in CLAUDE.md (no separate test-verifier), and already has a strong validator surface in the PR-time hook chain. The deliverables are scoped to what is genuinely missing.
- **Documented, not enforced.** The author considered an Edit-time PreToolUse hook that would gate the first edit in production directories on `/feature-factory` having run, but rejected it — the repo already stacks four PR-time skill gates, and adding a fifth universal pre-edit gate would compress to "press retry twice for every typo fix." `CLAUDE.md` + slash command is the lightest defaulting that still names the workflow.

## Alternatives considered

### Alternative 1: Install the `feature-dev` plugin (`code-explorer` + `code-architect`)

The Claude Code marketplace ships a `feature-dev` plugin with two agents that closely match Researcher + Spec Writer. Pulling that in would have skipped writing those agents by hand.

Rejected because: the plugin agents are generic; the storyteller-specific risk classes (prompt-variable contracts in `prompts/*.py` + `prompts/*_ru.py`, `db/converters.py` round-trip, scope-filtered `knowledge/`, EventManager interaction) need to be addressed by name in each agent prompt. A generic Researcher will miss them. The story-writer slot also has no plugin counterpart, so handwriting two of three was already on the table.

### Alternative 2: Edit-time enforcement hook

Add a PreToolUse hook on `Edit/Write/MultiEdit` that denies the first edit in production directories per session until `/feature-factory` has run. Strongest form of "default."

Rejected because: the repo already has four PR-time gates (`require-skill simplify` on `git commit`, `require-skill pr-review-toolkit_review-pr` on `gh pr create`, `require-skill decision-records` on `gh pr create`, `require-prompt-audit.sh` on `gh pr create`) plus three other Bash gates (`block-secrets.sh` on `git commit` — this PR, `check-git-push.sh` on `git push`, `protect-migrations.sh` on Edit/Write to committed Alembic revisions). Stacking another universal pre-edit gate would compress to noise and habituate retry-to-bypass on every session start. Documentation + slash command is the lightest defaulting that still names the workflow; the existing PR-time validator chain catches whatever the upstream chain misses.

### Alternative 3: Status quo (main session plays all roles)

Keep the existing setup; no upstream chain.

Rejected because: the contract-mismatch failure class documented in CLAUDE.md still happens — the existing `prompt-wiring-auditor` catches it at PR time but only after the broken wiring is already in the diff. Upstream catching is strictly cheaper.

## Consequences

Positive consequences:
- Producer→consumer prompt-variable contracts (EN+RU) are explicit in the brief before code is written.
- The "what does this design preserve, what does it amend?" question against accepted decision records is forced at the brief stage, not at PR time.
- The main session's context window stays focused on implementation, not on research + design + implementation simultaneously.
- The chain composes cleanly with the existing `decision-records` skill — no duplicate record content.

Tradeoffs / risks:
- For genuinely small changes that touch a production directory but don't warrant the chain, there is a judgment call. CLAUDE.md names the exception explicitly; agents will still over-trigger or under-trigger at the margin.
- The three upstream agents are new and untuned. Their prompts will need iteration as real features run through them. The `prompt-wiring-auditor` at PR time is the safety net.
- The "Backend Builder" role stays in the main session. If the main session drifts from CLAUDE.md discipline (e.g. skips the gauntlet), the PR-time gates catch it but later than a scoped builder would.

What future agents must preserve:
- The chain originally had **three human approval gates** (story, brief, PR). ADR-0014 supersedes the PR approval gate for low-risk green PRs: GitHub PR + CI visibility remains required, but agents may merge low-risk PRs without waiting for a separate human approval. Story/brief gates still apply when feature-factory is invoked.
- The Spec Writer **must** produce the prompt-variable contract table (producer kwarg key, consumer `required_vars`, EN status, RU status) when any prompt is touched. This is the table the `prompt-wiring-auditor` exists to verify; producing it upstream is the whole point of the upstream chain.
- The Spec Writer **points at** the `decision-records` skill; it does not embed decision-record content. Records are durable; briefs are per-feature.
- If you decide the chain is too heavyweight, supersede this ADR rather than silently removing the skill or agent files. The CLAUDE.md "Default workflow: feature-factory" section is the contract.

## Verification / tests

- The three agent files exist and declare the article's required output sections.
- `.claude/skills/feature-factory/SKILL.md` orchestrates the chain with both human gates explicit.
- `.claude/hooks/block-secrets.sh` correctly denies on `git commit` when the staged set includes `.env*`, `*.key`, `*.pem`, or `*secrets.json` (and allowlists `.env.{example,sample,template}`). Smoke-tested on both the staged-files branch and the path-mode-args branch.
- `CLAUDE.md` "Default workflow: feature-factory" section is present.
- The next real feature run through the chain should produce a brief whose prompt-variable contract table holds against `prompt-wiring-auditor` at PR time with zero `silent-drop` findings.

## Related files

- `.claude/agents/codebase-researcher.md`
- `.claude/agents/story-writer.md`
- `.claude/agents/spec-writer.md`
- `.claude/skills/feature-factory/SKILL.md`
- `.claude/hooks/block-secrets.sh`
- `.claude/settings.json`
- `CLAUDE.md`
- `.claude/agents/prompt-wiring-auditor.md` (the PR-time safety net the upstream chain is designed to satisfy without findings)
- `.claude/skills/decision-records/SKILL.md` (composed with, not duplicated)
