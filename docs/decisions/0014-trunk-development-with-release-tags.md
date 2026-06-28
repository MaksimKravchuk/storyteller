# ADR-0014: Trunk development with release tags

Date: 2026-06-28
Status: Accepted
Decision owner: Max
Related: `AGENTS.md`, `CLAUDE.md`, `docs/studio/03-release-checklist.md`

## Context

Storyteller uses Hermes Kanban and autonomous coding workers. The previous workflow treated most code changes as local worktree handoffs that waited for Max to approve before pushing or opening a PR. That preserved control, but it made review harder: code is easier to inspect, comment on, and merge as a GitHub PR than as a local diff hidden in a worker worktree.

The project also needs faster iteration. Max wants less operational control over routine engineering mechanics while keeping release boundaries explicit.

## Decision

Adopt trunk development with release tags:

- `main` is the trunk and the only long-lived development branch.
- Agents should use short-lived branches and open GitHub PRs early for review whenever code changes are involved.
- Opening a PR is considered part of the normal deliverable for code work, not a separate approval gate.
- Agents may merge low-risk PRs into `main` after required deterministic checks and CI pass.
- Product/release boundaries remain guarded: public releases, production deploys, release tags, paid/e2e benchmark runs, destructive data operations, and broad product-behavior changes still require Max approval unless explicitly delegated for that task.
- Releases are cut from `main` using annotated tags after the release checklist is satisfied.

## Rationale

- GitHub PRs provide the most convenient code review surface: file diffs, comments, checks, and links to issues/Kanban cards.
- Trunk development keeps branches short-lived and avoids a pile of abandoned worktrees.
- Auto-merging safe green PRs reduces Max's project-manager load while preserving visibility.
- Release tags separate integration from release: code can land continuously on `main`, while public release moments stay explicit.

## Alternatives considered

### Alternative 1: Local Kanban review before PR

Workers finish in a local worktree and block for human review before any push.

Rejected because it makes review inconvenient and slows routine code flow. Max explicitly prefers PR review for code changes.

### Alternative 2: Direct pushes to `main`

Agents commit straight to trunk without PRs.

Rejected as the default because PRs are still the best review and CI surface. Direct pushes may be used only when Max explicitly requests them for a narrow change.

### Alternative 3: Long-lived feature branches

Keep feature branches open across multiple tasks and merge later.

Rejected because this conflicts with trunk development, increases merge conflicts, and hides integration risk.

## Consequences

Positive consequences:
- Routine code work ends as a PR link by default.
- Max can review code in GitHub instead of local diffs.
- Low-risk fixes can move through PR → CI → merge without repeated approvals.
- Release tags become the explicit control point for what is shipped.

Tradeoffs / risks:
- Agents can merge more autonomously, so they must keep changes surgical and test evidence strong.
- More PRs may appear, but they should be small and short-lived.
- Mistaken classification of a high-risk PR as low-risk is the main failure mode; agents must stop and ask when behavior, release, data, or cost boundaries are involved.

What future agents must preserve:
- Open PRs early for code changes.
- Keep branches short-lived; do not accumulate long-running feature branches.
- Do not cut release tags, deploy publicly, or run paid/e2e/benchmark checks without Max approval.
- Use release tags from `main` for release boundaries.

## Verification / tests

- `AGENTS.md` and `CLAUDE.md` describe trunk development and PR autonomy.
- PRs include issue/card links and deterministic test evidence.
- Release PRs/tags reference `docs/studio/03-release-checklist.md`.

## Related files

- `AGENTS.md`
- `CLAUDE.md`
- `docs/studio/03-release-checklist.md`
