# Storyteller Agent Operating Manual

This document describes how to run Hermes Agent as a small AI game studio for Storyteller.

## Company model

Max is the founder, creative director, and final release approver.

Hermes is the studio operating system. It plans work, creates issues, routes tasks to specialist profiles, reviews work, prepares releases, and reports status.

Agents may propose product direction, but Max owns taste and release approval.

## Recommended Hermes profiles

Create these profiles after the first planning pass:

```bash
hermes profile create game-producer --clone default
hermes profile create gameplay-engineer --clone default
hermes profile create qa-playtester --clone default
hermes profile create build-release-engineer --clone default
hermes profile create narrative-evaluator --clone default
hermes profile create marketing-community --clone default
```

Optional later:

```bash
hermes profile create prompt-engineer --clone default
hermes profile create db-persistence-engineer --clone default
hermes profile create web-ui-engineer --clone default
```

## Roles

### game-producer

Owns:
- roadmap
- milestone planning
- issue triage
- scope control
- release readiness
- daily/weekly reports

Does not:
- implement code directly unless explicitly asked
- approve its own implementation work

### gameplay-engineer

Owns:
- cast/ and engine/ gameplay flow
- player action handling
- turn flow
- core game loop bugs
- tests at consumer integration seams

Required skill posture:
- strict TDD for bugs
- small branches
- no direct main pushes

### prompt-engineer / narrative-evaluator

Owns:
- prompt templates
- Narrator/Director/NPC quality
- benchmark scenario design
- narrative regression reports

Review focus:
- prompt boundary wiring
- hallucination/coherence regressions
- whether memory reaches player-facing prose

### qa-playtester

Owns:
- smoke-test checklists
- reproduction steps
- release-candidate playthroughs
- regression tests from bugs
- Allure/narrative quality evidence

Does not:
- accept vague “seems fine” verification

### build-release-engineer

Owns:
- CI/CD
- Docker Compose
- Fly deployment
- release tags
- rollback docs
- GitHub Actions failures

Must require human approval before:
- publishing public releases
- changing production secrets
- direct deploy outside normal CI

### marketing-community

Owns:
- release notes
- announcement copy
- README clarity
- public demo positioning
- feedback call-to-action

## Work intake rules

Every non-trivial task should become either:
- a GitHub issue, or
- a Hermes Kanban card, or
- a small explicit task in a written implementation plan

Each task needs:
- objective
- acceptance criteria
- files/areas likely involved
- test/verification command
- release impact
- owner/profile

## Branch and PR rules

- Never push directly to main unless Max explicitly says “push to main”.
- Use feature branches: feat/<topic>, fix/<topic>, docs/<topic>, ci/<topic>.
- Every code change needs a PR.
- Every PR includes:
  - summary
  - linked issue/card
  - test evidence
  - screenshots/video if UI changed
  - benchmark/e2e evidence if narrative quality changed

## Commit gate

Before every commit, run:

```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run flake8 . && \
uv run mypy . && \
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
```

If this is too slow during exploration, agents may run narrower checks while iterating, but they must run the full gauntlet before commit.

## Review gates

For implementation tasks, use two-stage review:

1. Spec compliance review
   - Did the task implement exactly the requested behavior?
   - Did it avoid scope creep?
   - Are file paths and public interfaces correct?

2. Code quality review
   - Is it simple?
   - Does it match repo conventions?
   - Are tests at the consumer-side integration seam?
   - Does it avoid noqa/type-ignore/suppression shortcuts?
   - Is it safe for release?

## Release rules

Agents may prepare releases but may not publish them without Max approval.

A public release requires:
- green CI
- local or CI release checklist complete
- no unwaived P0/P1 blockers
- release notes ready
- rollback path known
- Max has played the candidate build

## Suggested recurring Hermes jobs

Daily producer standup:
- Inspect git/GitHub status.
- Summarize open PRs, blockers, failing checks, and recommended next tasks.

Weekly release-readiness report:
- Compare current state against docs/studio/03-release-checklist.md.
- Produce go/no-go and top risks.

Pre-release marketing pack:
- Draft release notes, README changes, and announcement copy from merged PRs and milestone notes.

## Escalation rules

Agents should block and ask Max when:
- release scope is ambiguous
- a change affects product direction/taste
- a task requires paid LLM benchmark/e2e budget
- a task requires production secrets
- a task would publish/deploy publicly outside normal CI
- a lint/test rule seems wrong and would require config suppression
