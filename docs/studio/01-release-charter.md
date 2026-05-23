# Storyteller Release Charter

Date: 2026-05-23
Status: Draft
Owner: Max

## Decision needed

Pick the next release target:

1. Private playable demo
2. Public web demo
3. Public beta
4. Early-access launch
5. 1.0 release

Recommendation: target a Public Web Demo first.

Why: the repo already has a FastAPI player UI, Docker/Fly deployment, and CI. A web demo lets us test the core experience without solving every distribution/store problem.

## Proposed release: Public Web Demo v0.1

Goal: a new player can open the web UI, enter a setting, play a coherent text quest for several turns, and understand why Storyteller is different from a generic chatbot.

## Target audience

Primary:
- players interested in AI interactive fiction
- AI/game dev peers who can give product feedback

Secondary:
- potential collaborators, testers, and early community members

## Must-have product outcomes

- A player can start a new story from the web UI.
- The first scene is compelling and grounded in the requested setting.
- The player can take common actions: explore, move, talk, inspect, wait.
- NPCs behave consistently enough for a short session.
- The game remembers recent events and uses them in later narration.
- The session can survive normal backend persistence paths if persistence is enabled for the deployed flow.
- Failure modes are understandable; no raw tracebacks in player-facing UI.

## Must-have engineering outcomes

- CI green on main.
- Docker image builds.
- Fly deploy succeeds.
- Web health check passes.
- Unit test coverage gate respected.
- No direct pushes to main by agents.
- Release candidate built from a tagged commit or explicit PR merge.

## Must-have QA outcomes

- Smoke test script/checklist exists for the player web UI.
- At least 3 canonical demo scenarios are tested:
  - historical grounded setting
  - fictional/fantasy setting
  - edge-case weird setting
- Known P0/P1 issues are closed or explicitly waived by Max.
- One benchmark run is archived as release baseline.

## Must-have launch outcomes

- README has accurate quickstart and demo URL if public.
- Short release notes exist.
- Demo limitations are documented honestly.
- A short social/community announcement is drafted.
- Feedback channel is defined.

## Non-goals for v0.1 demo

- Steam/itch release.
- Mobile apps.
- Multiplayer.
- Full content moderation system.
- Perfect historical accuracy.
- Arbitrary long-running campaigns without memory degradation.
- Full visual art pipeline.
- Full monetization.

## Release blockers

- Main branch cannot deploy.
- Web UI cannot start a story.
- Common player action crashes server.
- API key/secrets leak into logs or UI.
- Cost runaway from a normal short play session.
- E2E/benchmark evidence shows severe narrative incoherence.

## Human approval gate

No public release is published until Max personally plays the candidate build and approves:
- story start
- 5+ turns of interaction
- one NPC interaction
- one persistence/reload path if applicable
- release notes and demo caveats
