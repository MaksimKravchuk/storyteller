# Storyteller AI Studio Roadmap

Date: 2026-05-23
Status: Draft
Recommended next milestone: Public Web Demo v0.1

## Milestone M0: Studio operating system

Goal: make the repo safe and legible for a Hermes-agent company.

Tasks:
- Add/maintain AGENTS.md with repo-specific agent rules.
- Create release checklist.
- Create issue/PR templates if missing or stale.
- Confirm GitHub auth/gh CLI path for issue and PR automation.
- Create Hermes profiles for specialist roles.
- Decide whether to use GitHub Issues, Hermes Kanban, or both.

Exit criteria:
- Agents know build/test commands.
- Agents know not to push to main.
- Every task has a clear owner and quality gate.

## Milestone M1: Release candidate baseline

Goal: know whether current main is releasable.

Tasks:
- Run full local quality gauntlet.
- Run Docker Compose stack locally.
- Smoke-test web UI at localhost:8070.
- Smoke-test admin UI at localhost:8080.
- Check Fly deployment status.
- Run one benchmark scenario if API keys/cost budget allow.
- Write a release-candidate gap report.

Exit criteria:
- A concrete blocker list exists.
- Each blocker is labeled P0/P1/P2.

## Milestone M2: Core player loop hardening

Goal: make a short demo session consistently good.

Tasks:
- Define 3 canonical demo scenarios.
- Add/verify smoke tests for starting a story.
- Add/verify tests for common action classification and turn flow.
- Inspect prompt wiring at consumer boundaries for Narrator, NPCs, and memory.
- Improve player-facing error handling if raw errors leak.
- Add or update demo-seed documentation.

Exit criteria:
- 3 demo scenarios can be played for 5+ turns each without crash.
- Narrative quality is acceptable enough for public feedback.

## Milestone M3: Web demo polish

Goal: make first-time player experience understandable.

Tasks:
- Review landing/start screen copy.
- Add instructions/examples for setting prompts.
- Add loading/progress affordances if slow LLM calls feel broken.
- Check mobile/narrow viewport basics.
- Ensure error states explain what happened.
- Update README with web demo flow.

Exit criteria:
- New player can understand what to do without reading source docs.

## Milestone M4: Release engineering

Goal: make deploy/release repeatable.

Tasks:
- Confirm Docker image build and healthcheck.
- Confirm Fly deploy secrets and runtime env.
- Document rollback path.
- Create release notes template.
- Decide version/tag format.
- Confirm CI required checks and branch protection.

Exit criteria:
- Release candidate can be deployed and rolled back predictably.

## Milestone M5: Launch package

Goal: publish the demo with clear positioning and feedback loop.

Tasks:
- Draft announcement.
- Draft changelog/release notes.
- Create short demo script or GIF checklist.
- Document known limitations.
- Create feedback issue template or form.

Exit criteria:
- Max approves public post and release notes.

## Suggested priority order

1. M0: studio operating system
2. M1: release candidate baseline
3. Fix P0/P1 blockers from M1
4. M2: core player loop hardening
5. M3/M4 in parallel
6. M5
