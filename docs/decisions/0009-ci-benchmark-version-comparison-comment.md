# ADR-0009: CI benchmark version-over-version comparison comment (advisory)

Date: 2026-05-31
Status: Accepted
Decision owner: Max
Related: ADR-0002 (`docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`), ADR-0003 (`docs/decisions/0003-engine-temperature-pinning-in-benchmark-mode.md`), `.github/workflows/benchmark-on-pr.yml`, `.github/workflows/benchmark-baseline.yml`, `benchmarks/cli/_narration_diff.py`

## Context

ADR-0002 turned `benchmarks run` into a regression gate: it auto-compares each scenario's fresh aggregate against the git-tracked pinned baseline under `benchmarks/baselines/<scenario_id>.json` and exits `1` on a real (k-sigma) regression. `benchmark-on-pr.yml` already runs that command on narrative-affecting PRs.

But the score verdict alone is a thin signal for a reviewer of a narrative PR. A `regression`/`improvement`/`noise`/`no_baseline` verdict and a single mean tells you *that* something moved; it does not tell you *which rubric element* moved or *how the prose actually changed*. Reviewers were left to either trust the one-line verdict or pull the artifacts and eyeball two runs by hand — the same eyeball job ADR-0002 set out to eliminate, displaced one level down from "is this a regression?" to "what regressed, and is the new prose actually worse?"

Three facts shaped the design:

1. The pinned baselines under `benchmarks/baselines/` carry a per-scenario *aggregate* (scores), not narration text. They are deliberately small, git-tracked, and reviewable in the PR diff. They cannot show what the prose used to read like.
2. Narration text for a "previous version" has to come from *somewhere* that is not the git-tracked baseline — the baseline does not store prose, and storing full narration in git would bloat the repo and churn the diff on every run.
3. The PR gate's `paths:` filter means the `benchmark` job does not run at all on PRs that don't touch `cast/`, `prompts/`, `engine/`, or `benchmarks/scenarios/`. A required branch-protection check on such a job strands every non-narrative PR waiting for a status that never arrives.

## Decision

Post a single **advisory** PR comment on narrative-affecting PRs that combines three components, and stand up a separate main-push workflow that produces the "previous version" narration content the comment needs.

1. **Score verdict (vs git-tracked baselines).** `benchmark-on-pr.yml` runs `benchmarks run --iterations 1 --max-judges 3`, tees stdout, and `grep`s the `[auto-compare]` lines into the comment. This is exactly the ADR-0002 auto-compare result against the git-tracked pinned baselines — `no_baseline` until a scenario is pinned, non-blocking by design.
2. **Per-element score deltas.** For each fresh `*_aggregate.json` whose `scenario_id` has a pinned baseline, the workflow extracts `.aggregate` from `benchmarks/baselines/<scenario_id>.json` and runs `benchmarks compare <base_agg> <current>`, collected under a `<details>` block.
3. **Narration-text diff.** A new CLI subcommand `benchmarks narration-diff <previous_dir> <current_dir>` (`benchmarks/cli/_narration_diff.py`) pairs per-iteration archives by `scenario_id` + turn `index` and renders a labelled previous/current blockquote diff per changed turn. The `<previous_dir>` is downloaded from the `benchmark-baseline` artifact produced by `benchmark-baseline.yml` on the most recent successful main push. When the artifact is missing or expired, the diff degrades gracefully to a current-only listing.

The previous-version content comes from a dedicated **`benchmark-baseline.yml`** workflow that mirrors the PR gate's `paths:` trigger on pushes to `main`, runs `benchmarks run --iterations 1 --max-judges 3 --no-compare`, and uploads `benchmarks/results/` as the `benchmark-baseline` artifact (90-day retention). `--no-compare` keeps it observational — it never gates main and never pins.

**The comment is deliberately advisory, never blocking.** The job runs `benchmarks run` under `set -uo pipefail` (no `-e`), captures `PIPESTATUS`, and prints the exit code without propagating it; the job stays green even on a scored regression. This is *not* a reversal of ADR-0002's exit-1 contract — the CLI still exits `1` on a real regression, and that contract remains intact and usable as a blocking gate in any context without a `paths:` filter. The PR *comment* is advisory because of the `paths:`-filter stranding problem above: a required check on a path-filtered job blocks unrelated PRs forever. The signal is the comment a reviewer reads before merging a narrative PR, not a red check.

## Rationale

- **Three signals answer three different questions.** The verdict answers "did the score move past noise?"; the per-element deltas answer "which rubric dimension moved?"; the narration diff answers "is the new prose actually worse, or just different?" A reviewer needs all three to judge a narrative change, and bundling them in one comment is cheaper than three artifact pulls.
- **The narration diff must not live in git.** Full per-turn narration for every scenario would bloat the repo and churn the PR diff on every engine roll (engine temperature is only pinned when ADR-0003's override is set; PR runs do not set it). An ephemeral, retention-bounded CI artifact is the right home for content that exists only to be *displayed*, never to *decide*.
- **Advisory is the honest posture for a path-filtered narrative check.** A required check that never fires on non-narrative PRs would either block every such PR or force a no-op shim. Treating the comment as the signal keeps the gate present where it matters and invisible where it doesn't.
- **Separating "gate reference" from "display content" is the whole point.** The pass/fail reference stays the small, git-tracked, PR-diff-visible baseline (ADR-0002). The artifact is a large, ephemeral, content-only convenience. Conflating them — using the artifact as the reference, or auto-pinning it — would silently re-grant the engine the ability to move its own bar, which is precisely ADR-0002 Alternative 4.

## Alternatives considered

### Alternative 1: Make the comparison a required (blocking) status check

Promote `benchmark-on-pr / benchmark` to a required branch-protection check and fail the job on a scored regression.

Rejected because the workflow's `paths:` filter means it never runs on PRs that don't touch the listed narrative paths. A required check on a job that never starts leaves every non-narrative PR blocked indefinitely on a status that never posts. Dropping the `paths:` filter to fix that would spend paid-LLM budget on every PR regardless of relevance. Advisory keeps the gate scoped to the PRs it can actually evaluate.

### Alternative 2: Use the `benchmark-baseline` artifact as the pass/fail reference (and/or auto-pin on main push)

Have the PR gate score against the previous-version artifact instead of the git-tracked baseline, and/or have `benchmark-baseline.yml` pin a new baseline after each green main push.

Rejected because it collapses ADR-0002's git-tracked-baseline review checkpoint. The artifact is unreviewed (it is whatever the last main push rolled), expires after 90 days, and is not visible in any PR diff. Scoring against it, or auto-pinning from it, would let the engine drift its own reference upward on a lucky main-push roll with no human in the loop — exactly the silent ratchet ADR-0002 Alternative 4 rejected. The artifact is content-only and feeds the narration *display* solely; the gate reference stays `benchmarks/baselines/*.json`.

### Alternative 3: Store previous-version narration in git alongside the baseline

Extend the pinned baseline (or add a sibling file) to carry the full narration text so the diff needs no artifact.

Rejected because narration text is large and churns on every non-deterministic engine roll, bloating the repo and the PR diff for content whose only job is to be displayed. ADR-0002 keeps baselines small and diff-reviewable on purpose; folding prose into them defeats that. An ephemeral artifact is the correct home.

## Consequences

Positive consequences:
- Reviewers of narrative PRs get verdict + per-element deltas + prose diff in one comment, without pulling artifacts.
- The gate reference stays git-tracked and PR-diff-visible; the comment adds context without touching the pass/fail mechanism.
- The narration-diff renderer is deterministic and side-effect free, so it is unit-testable without hitting LLMs.
- Fork PRs degrade safely: with `pull_request` (not `pull_request_target`), secrets are absent and the token is read-only, so the LLM calls and comment fail silently — no leak, no false signal.

Tradeoffs / risks:
- The narration diff depends on a fresh `benchmark-baseline` artifact existing on main. If none has run (or it expired past 90 days), the diff degrades to a current-only listing — informative but not a comparison.
- The previous-version content reflects the last main push, which may lag the actual merge base of the PR. The diff is a "previous main → this PR" view, not a strict merge-base diff; the comment header says so.
- An advisory comment can be ignored. The mitigation is process (read the comment before merging a narrative PR), not enforcement — by design, given the path-filter constraint.
- Each PR push and each qualifying main push hits paid LLMs (~$0.02–$0.10); `concurrency: cancel-in-progress` limits this to the HEAD commit.

What future agents must preserve:
- **The pass/fail reference is the git-tracked baseline, never the artifact.** The score gate compares the fresh aggregate against `benchmarks/baselines/<scenario_id>.json`. Do not point the gate at the `benchmark-baseline` artifact, and do not derive the verdict from artifact content.
- **The `benchmark-baseline` artifact is content-only.** It exists to feed the narration-diff *display*. It must never become the gate reference and must never be `pin`-ed.
- **No auto-pin on main push.** `benchmark-baseline.yml` runs `--no-compare`, uploads `benchmarks/results/`, and never writes `benchmarks/baselines/`. Baselines change only via the explicit human-gated `benchmarks pin` / `benchmarks run --update-baselines-on-improvement` path (ADR-0002). This keeps ADR-0002 Alternative 4 (auto-pin every green main run) in force as rejected.
- **The CLI exit-1 contract from ADR-0002 is preserved.** `benchmarks run` still exits `1` on a real regression. `benchmark-on-pr.yml` deliberately does not propagate that exit code into the job result — that is a workflow-level advisory choice, not a change to the CLI gate. Any context without a `paths:` filter may still use the exit code as a blocking gate.
- **The PR comment stays advisory.** Do not make `benchmark-on-pr / benchmark` a required branch-protection check while the `paths:` filter is present (it would strand non-narrative PRs).

## Verification / tests

- `tests/test_benchmarks_narration_diff.py` — 16 tests covering `build_turn_index` (turn extraction, first-iteration-wins, aggregate skip, missing/unsuffixed scenario id) and `format_report` (unchanged / changed / new-scenario / no-baseline / new-turn-index / removed-turn / multiline blockquote / empty-current), plus the CLI seam (prints report, missing previous dir, missing current path → exit 2).
- `.github/workflows/benchmark-baseline.yml` — runs `benchmarks run --no-compare` on main pushes to narrative paths and uploads the `benchmark-baseline` content-only artifact. The header comment and the `--no-compare` flag (no `pin` call, uploads `benchmarks/results/` not `benchmarks/baselines/`) are the guardrail that this never pins.
- `.github/workflows/benchmark-on-pr.yml` — builds the three-part comment: `grep '^\[auto-compare\]'` for the verdict, a per-scenario `benchmarks compare` loop against `benchmarks/baselines/*.json`, and `benchmarks narration-diff prev_content benchmarks/results`. The job runs under `set -uo pipefail` (no `-e`) and never fails on a regression; the comment footer cites ADR-0002 / ADR-0009 as advisory.
- The ADR-0002 auto-compare, baseline round-trip, and ratchet tests are *not* re-claimed here — they protect the gate mechanism this ADR builds on, not the comment/artifact layer this ADR adds.
- Local gauntlet (ruff, ruff format, flake8, mypy, pytest excluding e2e/benchmarks) must pass before commit — this branch carries new and modified Python under `benchmarks/cli/`, not just the ADR.

## Related files

- `benchmarks/cli/_narration_diff.py`
- `benchmarks/cli/_narration_diff_format.py`
- `benchmarks/cli/_narration_diff_model.py`
- `benchmarks/cli/_iteration_archives.py`
- `benchmarks/cli/_args_subcommands.py`
- `benchmarks/cli/_dispatch.py`
- `.github/workflows/benchmark-on-pr.yml`
- `.github/workflows/benchmark-baseline.yml`
- `benchmarks/baselines/` (git-tracked pass/fail reference — ADR-0002)
- `tests/test_benchmarks_narration_diff.py`
- `docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`
