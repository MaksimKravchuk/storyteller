# Initial Backlog for AI Studio Setup

This is a starter backlog. Convert these to GitHub issues or Hermes Kanban cards after Max confirms the release target.

## P0: Studio setup

### Issue: Confirm release target and non-goals

Owner: game-producer
Labels: type:planning, priority:p0

Acceptance criteria:
- docs/studio/01-release-charter.md has a chosen release target.
- Non-goals are explicit.
- Max has approved the charter.

### Issue: Verify current main quality gate

Owner: qa-playtester
Labels: type:qa, priority:p0

Acceptance criteria:
- Full local quality command result is recorded.
- Any failures are filed as separate issues with logs.

### Issue: Verify local Docker Compose runtime

Owner: build-release-engineer
Labels: area:build, area:release, priority:p0

Acceptance criteria:
- docker compose up -d succeeds.
- Web healthcheck passes at localhost:8070/healthz.
- Admin healthcheck passes at localhost:8080/healthz.
- Startup logs are checked for obvious errors.

### Issue: Create canonical demo scenario list

Owner: narrative-evaluator
Labels: area:narrative, type:qa, priority:p0

Acceptance criteria:
- Three demo scenarios are listed in docs/studio/03-release-checklist.md.
- Each scenario has expected qualities and red flags.

## P1: Release hardening

### Issue: Add player web UI smoke checklist or automated smoke test

Owner: qa-playtester
Labels: area:web, type:test, priority:p1

Acceptance criteria:
- A tester can follow the smoke checklist without source-code knowledge, or an automated smoke test covers the basic flow.
- The smoke gate includes story start, 5 turns, NPC interaction, and no raw traceback.

### Issue: Audit player-facing error handling

Owner: gameplay-engineer
Labels: area:web, area:gameplay, type:bug, priority:p1

Acceptance criteria:
- Common provider/API/database failures do not expose raw tracebacks to players.
- Tests cover at least one important failure path.

### Issue: Confirm Fly.io release and rollback procedure

Owner: build-release-engineer
Labels: area:release, priority:p1

Acceptance criteria:
- Release procedure is documented.
- Rollback procedure is documented.
- Required secrets are listed by name only, not value.

### Issue: Draft public demo release notes

Owner: marketing-community
Labels: area:marketing, priority:p1

Acceptance criteria:
- Release notes explain what Storyteller is.
- Known limitations are honest.
- Feedback channel is clear.

## P2: Product polish

### Issue: Review first-time web UX copy

Owner: marketing-community
Labels: area:web, area:marketing, priority:p2

Acceptance criteria:
- Start screen explains what to enter.
- At least three example setting prompts are provided.
- Loading states are understandable.

### Issue: Add benchmark baseline for release candidate

Owner: narrative-evaluator
Labels: area:benchmarks, area:narrative, priority:p2

Acceptance criteria:
- One benchmark run is archived.
- Any major narrative regression is filed as an issue.
- Cost/API usage is approved before running.
