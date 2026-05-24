# Storyteller Friends Beta GTD Plan

Release target: **Friends Beta v0.2**  
Status: Draft operating plan  
Owner/final approver: Max  
Studio operator: Hermes

## Goal

Ship an invite-only beta that friends can install as a PWA, sign into, play across devices, and give feedback on — while Storyteller controls LLM spend and records enough telemetry to make a later subscription decision.

## Product definition

A beta tester should be able to:

1. Receive an invite.
2. Open Storyteller on desktop or mobile.
3. Install it as a PWA.
4. Sign in with an invited account.
5. Start a story.
6. Continue prior stories from the same account.
7. Play at least 10 turns without raw errors.
8. Submit feedback tied to the game/turn.

## Non-goals

- Native iOS/Android apps.
- Open public signup.
- Stripe subscriptions or public paid launch.
- Unlimited gameplay.
- Multiplayer.
- Full content moderation system.
- Perfect offline gameplay.
- Broad marketing launch.

## Operating principles

- Founder/game-design decisions come from Max.
- Hermes owns execution, issue tracking, PRs, checks, and release preparation.
- Every implementation PR must state player-visible impact.
- Docs/process work is useful but not counted as gameplay/product progress unless it directly enables beta execution.
- Public deploys, tester invitations, billing changes, and release announcements require Max approval.

## Workstreams

### 1. PWA installability

Outcome: Storyteller can be installed and launched like an app.

Deliverables:

- Web app manifest.
- App icons.
- Service worker.
- Offline/poor-network shell message.
- Install instructions in onboarding docs.
- Tests/checklist for PWA assets and service-worker route.

### 2. Supabase Auth + invite gate

Outcome: invited testers can sign in; uninvited users cannot consume beta gameplay budget.

Deliverables:

- Supabase configuration via env vars.
- Auth/session verification in FastAPI.
- Invite/allowlist model.
- Login/logout UI.
- Protected game APIs.
- Tests for unauthenticated, uninvited, invited, and cross-user access.

### 3. Account-owned stories

Outcome: games belong to accounts and can be resumed across devices.

Deliverables:

- User/account mapping.
- `sessions` ownership by user.
- Game list endpoint.
- "My stories" UI.
- Continue/archive/delete flows.
- Migration behavior for existing anonymous-cookie sessions if retained.

### 4. Cost telemetry and quotas

Outcome: beta spend is measurable and bounded.

Deliverables:

- AI call logs attributable to user/session/game.
- Pricing config for active models.
- Per-user cost and turn summaries.
- Daily/weekly turn quotas.
- Max active games quota.
- Global beta kill switch.
- Friendly quota-exceeded and provider-unavailable messages.

### 5. Feedback and beta operations

Outcome: feedback is easy for testers and actionable for Max.

Deliverables:

- In-app feedback form.
- Feedback storage with user/game/turn context.
- Admin/report view or export.
- Tester invite copy.
- PWA install instructions.
- Known limitations.
- Lightweight privacy/beta disclaimer.

### 6. Subscription readiness, not billing

Outcome: later subscription pricing can be based on real telemetry.

Deliverables:

- Plan/entitlement concept (`friend_beta`, `admin`, future paid tiers).
- Quotas tied to plan.
- Cost-per-session reporting.
- Pricing hypothesis doc after beta telemetry.

Deferred:

- Stripe Checkout.
- Customer portal.
- Payment webhooks.

## Milestone gates

### Gate 1 — Plan/backlog ready

- [ ] Friends Beta v0.2 GitHub milestone exists.
- [ ] P0/P1 issues created with acceptance criteria.
- [ ] Founder decision register exists.
- [ ] Auth provider default recorded.

### Gate 2 — Core beta build ready

- [ ] PWA installability merged.
- [ ] Auth/invite gate merged.
- [ ] Account-owned stories merged.
- [ ] Cost telemetry merged.
- [ ] Quotas/kill switch merged.
- [ ] Feedback form merged.

### Gate 3 — QA ready

- [ ] Local quality gate passes.
- [ ] CI green.
- [ ] Docker Compose starts.
- [ ] Web health and readiness checks pass.
- [ ] Account isolation tests pass.
- [ ] Quota tests pass.
- [ ] PWA checklist passes.

### Gate 4 — Founder playtest

- [ ] Max signs in as beta user.
- [ ] Max installs/opens PWA.
- [ ] Max starts one story.
- [ ] Max plays 10+ turns.
- [ ] Max submits feedback.
- [ ] Max approves Wave 1 invites.

### Gate 5 — Wave 1 beta

- [ ] Invite 5 testers.
- [ ] Monitor cost/errors daily.
- [ ] Review feedback.
- [ ] Fix P0/P1 beta blockers only.
- [ ] Decide whether to expand to Wave 2.

## Suggested PR order

1. Docs/backlog PR: Friends Beta charter, decision register, GTD plan.
2. PWA PR: manifest, icons, service worker, offline shell.
3. Auth foundation PR: Supabase JWT/session verification and invite gate.
4. Account ownership PR: users, session ownership, cross-user access tests.
5. Game library PR: list/continue/archive/delete stories.
6. Cost telemetry PR: user-attributed token/cost reports.
7. Quotas PR: limits, kill switch, friendly UI messages.
8. Feedback PR: in-app feedback with game/turn context.
9. Beta admin docs PR: invite copy, privacy note, known limitations, tester guide.
10. Release candidate PR: final checklist updates and evidence.

## Max decisions needed before release

See `docs/studio/09-founder-decision-register.md`.

Current blocking decisions before inviting friends:

- Confirm initial cost budget.
- Confirm privacy/contact channel.
- Approve beta success criteria.
- Approve Wave 1 tester list.
