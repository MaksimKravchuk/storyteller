# Founder Decision Register

Release target: Friends Beta v0.2  
Owner: Max  
Studio operator: Hermes  
Last reviewed: 2026-05-25

This file records founder/game-design/product decisions that agents must not invent silently. Hermes may recommend defaults and continue execution when the default is low-risk, but items marked **Max decision required** block release until Max confirms them.

This register is the current Storyteller convention for founder/product/release decisions. Architecture or implementation ADRs may also live under `docs/decisions/`; before changing release strategy, beta scope, pricing/subscriptions, privacy posture, or approval authority, inspect this register and preserve accepted constraints unless Max explicitly supersedes them.

## Decision states

- **Chosen** — current operating decision.
- **Defaulted** — Hermes is proceeding with this default; Max can override.
- **Max decision required** — do not ship/release this item until Max decides.
- **Deferred** — explicitly out of current milestone.

## Record format

Each durable decision should capture:

- **Context** — what pressure/problem created the decision.
- **Decision** — the current operating choice.
- **Rationale** — why this is the right choice now.
- **Alternatives considered** — credible options and why they were not selected.
- **Consequences / guardrails** — what this enables, risks, and what future agents must preserve.
- **Verification** — what proves the decision is implemented or still respected.

## D001 — Beta release target

Status: **Chosen**

Context:

- Storyteller needs real player feedback before a broad launch or paid acquisition.
- The beta milestone must validate the product loop, not only the technical demo.

Decision:

- Target **Friends Beta v0.2** before any broad public launch.

Rationale:

- The product needs real friend/player feedback before paid acquisition or subscriptions.
- Invite-only access gives cost control while the AI gameplay loop is still being hardened.
- The milestone can validate PWA installability, accounts, persistence, cost telemetry, quotas, and feedback loops.

Alternatives considered:

- **Broad public launch first** — rejected because cost, quality, support, and data/privacy risks are too high before friendly tester feedback.
- **Private solo testing only** — rejected because it cannot validate onboarding, retention, account flows, or whether non-authors understand the gameplay loop.

Consequences / guardrails:

- Agents should prioritize beta readiness over public-launch polish.
- Do not treat docs-only or internal prep work as equivalent to player-visible beta progress.
- Do not expand audience beyond the approved beta scope without Max approval.

Verification:

- Release checklist and roadmap reference Friends Beta v0.2 as the active target.
- PRs for release work should explain whether they advance beta readiness.

## D002 — Auth provider

Status: **Defaulted**

Context:

- Friends Beta needs account identity, persistence ownership, invite gating, and later per-user cost/feedback correlation.
- Building secure custom auth would distract from validating gameplay.

Decision:

- Use **Supabase Auth** for Friends Beta unless Max overrides before implementation starts.

Rationale:

- Fast beta path for email/social auth without owning password-reset/security workflows.
- Production-ish session model and account lifecycle.
- Avoids turning the beta milestone into a custom auth/security project.

Alternatives considered:

- **Custom username/password auth** — rejected because password reset, account security, and abuse handling are not beta differentiators.
- **Clerk** — viable fallback, but Supabase aligns better with possible database/backend integration and keeps the default stack simple.
- **Google OAuth-only** — simpler, but excludes testers who prefer email/password and is less flexible for invite flows.
- **Temporary invite-code accounts** — faster for a throwaway demo, but weaker for durable save ownership and feedback/cost attribution.

Consequences / guardrails:

- Store only Supabase user identifiers and Storyteller account/profile metadata needed by the product.
- Keep all Supabase URLs/keys in environment variables; never commit secrets.
- Gate beta play behind invited/allowlisted accounts.
- Max may still override the provider before implementation starts.

Verification:

- Auth/account PRs should show environment-based configuration, invite gating, and no committed secrets.
- Tests should cover account-to-game ownership and unauthorized access denial.

## D003 — Beta audience size

Status: **Defaulted**

Context:

- LLM gameplay has variable cost and quality.
- The team needs enough testers for signal without exposing the system to uncontrolled spend or support load.

Decision:

- Roll out in waves:
  - Wave 1: 5 invited testers.
  - Wave 2: 10–15 testers after cost/error review.
  - Wave 3: 25–30 testers only after quotas and telemetry look safe.

Rationale:

- Small initial cohorts make cost/error patterns reviewable.
- Wave gates preserve founder control while still creating a path to broader feedback.

Alternatives considered:

- **Invite everyone at once** — rejected due to cost, reliability, and support risk.
- **Only one or two testers** — rejected because the sample is too small to validate onboarding and replay interest.
- **Fully public waitlist** — deferred until cost controls and quality evidence exist.

Consequences / guardrails:

- Do not invite Wave 2+ until Wave 1 has at least one reviewed cost/error report.
- Agents may prepare tooling for later waves, but must not publish/invite beyond approved scope.

Verification:

- Admin/cost reports should support reviewing Wave 1 before expansion.
- Release notes or onboarding docs should identify the active wave and tester count.

## D004 — Cost budget

Status: **Defaulted**

Context:

- AI gameplay calls paid model APIs and can run away without quotas.
- The beta needs enough room for meaningful play while protecting Max from surprise spend.

Decision:

- Initial global beta LLM budget: **$50**.
- Per-user daily quota: **20 turns**.
- Per-user weekly quota: **50 turns**.
- Max active games per user: **3**.
- Public/guest play remains limited or disabled until cost telemetry is verified.

Rationale:

- Existing `ai_call_logs` already records token counts, so beta work should convert this into per-user cost telemetry and enforceable quotas.
- The app should fail closed with friendly quota/provider messages, not silent runaway spend.

Alternatives considered:

- **No quota for friendly testers** — rejected because model spend can spike and early bugs may loop calls.
- **Very strict quotas below 10 turns/day** — rejected because testers need enough turns to experience a real session.
- **Paid subscriptions before beta** — rejected by D005; pricing should follow observed cost and retention.

Consequences / guardrails:

- Quota and telemetry work is release-critical for Friends Beta.
- UX must explain quota/provider failures gracefully.
- Public/guest play should not bypass the budget model.

Max decision required before release:

- Confirm or adjust the $50 initial budget.

Verification:

- Admin reports expose spend/usage by user and time window.
- Tests cover quota enforcement and friendly quota exhaustion responses.

## D005 — Subscription timing

Status: **Chosen**

Context:

- Storyteller does not yet have reliable beta cost/session, retention, or willingness-to-pay data.
- Billing introduces operational, support, legal, and tax complexity.

Decision:

- Do **not** build Stripe subscriptions before Friends Beta.
- Build now:
  - Account plans/entitlements.
  - Quotas.
  - Cost telemetry.
  - Admin reports.
- Defer:
  - Stripe Checkout.
  - Customer portal.
  - Payment webhooks.
  - Tax/VAT policy.

Rationale:

- Pricing should be based on actual beta cost/session and retention.
- Premature billing adds operational and support burden before product-market feedback.

Alternatives considered:

- **Add Stripe immediately** — rejected because it slows beta and creates support obligations before pricing is validated.
- **No entitlement model at all** — rejected because quotas and later subscriptions need a clean internal plan boundary.
- **Manual payments/donations** — deferred because it does not solve core subscription/product validation yet.

Consequences / guardrails:

- Agents should build subscription-ready seams, not billing flows.
- Do not add payment collection, Stripe webhooks, or customer portal work unless Max explicitly changes this decision.
- Cost telemetry must be strong enough to inform future pricing.

Verification:

- Beta PRs may include plans/entitlements/quotas, but should not add Stripe runtime dependencies or payment routes.
- Release checklist confirms subscriptions are deferred.

## D006 — PWA offline behavior

Status: **Chosen**

Context:

- A PWA install prompt improves mobile/desktop beta UX.
- Actual gameplay depends on server state and model access, so offline play would be misleading and expensive to implement.

Decision:

- PWA should be installable, but gameplay is **online-required**.

Rationale:

- Installability gives testers an app-like entry point without pretending the AI game can run locally/offline.
- Clear offline messaging avoids false expectations and support issues.

Alternatives considered:

- **Full offline gameplay** — rejected because model calls, persistence, and dynamic world state require network/server access.
- **No PWA support** — rejected because beta testers benefit from installable app ergonomics.
- **Offline read-only replay** — deferred as non-essential for Friends Beta.

Consequences / guardrails:

- Do not claim offline gameplay in UI, docs, release notes, or manifest text.
- Offline state should explain that Storyteller needs internet/model access to continue.

Verification:

- Installed app shell opens.
- Offline state is friendly and explicit.
- PWA tests or smoke notes verify installability without offline gameplay claims.

## D007 — Data/privacy posture

Status: **Defaulted**

Context:

- Friends Beta stores player-generated content, game state, feedback, and account identifiers.
- AI requests may be sent to third-party model providers.
- Friendly testers still need clear expectations about logs and deletion.

Decision:

- Friends Beta privacy notice must say:
  - Story prompts, player actions, generated narration, feedback, and account identifiers may be stored.
  - AI requests are sent to model providers.
  - Logs may be reviewed by Max/Hermes for debugging, product quality, and safety.
  - Testers should not enter sensitive personal data.
  - Testers can ask for deletion of their account/game data.

Rationale:

- Honest privacy framing reduces tester surprise and supports responsible debugging.
- The beta should avoid collecting sensitive data it does not need.

Alternatives considered:

- **No explicit privacy notice for friends** — rejected because beta data still includes personal/account and creative content.
- **Formal legal policy before beta** — deferred unless required, because a concise beta notice is enough for limited friends testing pending Max approval.
- **Do not store prompts/logs** — rejected because debugging, continuity, safety, and quality review need retained data.

Consequences / guardrails:

- Do not encourage testers to enter sensitive personal data.
- Deletion request handling must be defined before release.
- Logs should be used for debugging, product quality, and safety, not unrelated purposes.

Max decision required before release:

- Confirm the public contact channel/email for privacy/deletion requests.

Verification:

- Beta onboarding/privacy UI includes the listed disclosures.
- Account/game deletion path or documented manual process exists before release.

## D008 — Feedback channel

Status: **Defaulted**

Context:

- The beta needs structured feedback tied to user/game context.
- External issue/chat mirroring can come later once signal volume and triage workflow are understood.

Decision:

- Add in-app feedback first; optionally mirror/triage to GitHub or a private chat later.
- Required feedback payload:
  - user id (do not duplicate email or other PII on the feedback row; look up account fields from the account record on demand to keep PII copies minimal per D007)
  - game id
  - turn number if available
  - category
  - free text
  - timestamp

Rationale:

- In-app feedback reduces tester friction and preserves context around the play session.
- Structured payloads make beta feedback actionable for product and QA follow-up.

Alternatives considered:

- **GitHub issues only** — rejected because friends/beta testers may not use GitHub and issue creation loses game context.
- **Private chat/DM only** — rejected because it is hard to correlate with game state and triage systematically.
- **No feedback form until after beta** — rejected because feedback is the point of the beta.

Consequences / guardrails:

- Feedback storage should avoid unnecessary sensitive data.
- Future mirroring must preserve privacy and avoid exposing tester/game details publicly.

Verification:

- Feedback submission persists the required fields.
- Admin/review path lets Max/Hermes inspect feedback by user/game/time.

## D009 — Game design: beta success criteria

Status: **Max decision required**

Context:

- Engineering can define functional readiness, but Max owns the subjective bar for whether the game experience is good enough.
- Without explicit success criteria, agents may optimize for checklists instead of player value.

Decision:

- Max should define or approve the subjective bar for a successful beta session.

Hermes default proposal:

- A new tester can install/open the app, sign in, start a story, play 10 turns, interact with at least one NPC, and submit feedback without help.
- At least 60% of Wave 1 testers complete one 10-turn session.
- At least 3 testers say they want to play another session.
- No P0 crashes or cross-user data leaks.
- Average model cost per 20-turn session stays under the budget model used for subscription planning.

Rationale:

- The beta should validate player comprehension, engagement, reliability, safety, and cost together.
- Completion and replay-interest metrics provide a practical proxy for early product pull.

Alternatives considered:

- **Pure engineering success criteria** — rejected because a technically stable but boring/confusing game is not a successful Storyteller beta.
- **Pure subjective vibes** — rejected because agents need measurable gates for release prep.
- **Retention-only metrics** — deferred until there are enough testers and sessions for retention to mean something.

Consequences / guardrails:

- Do not declare beta release-ready until Max approves or revises the success bar.
- QA and release notes should report against the approved criteria, not just passing tests.

Verification:

- Release checklist includes Max-approved success criteria.
- Beta report compares Wave 1 outcomes against the criteria.

## D010 — Release approval

Status: **Chosen**

Context:

- Hermes and specialist agents can prepare significant work autonomously.
- Release/publication decisions affect users, spend, reputation, and data/privacy obligations.

Decision:

- Max remains final approver.
- Agents may prepare PRs, release candidates, docs, deploy procedures, and private staging checks.
- Agents must not publish/invite testers beyond approved scope or merge/deploy release-critical changes without Max approval.

Rationale:

- Max is founder/creative director and owns product/release judgment.
- Agent autonomy is useful for execution, but not for irreversible release or audience-expansion decisions.

Alternatives considered:

- **Agents fully own release** — rejected because release scope, tester invites, spend, and public commitments need founder approval.
- **Agents only suggest, never prepare** — rejected because it wastes the studio operating model; agents should prepare artifacts for approval.
- **Auto-merge all green PRs** — rejected for release-critical changes because passing checks do not replace product approval.

Consequences / guardrails:

- Agents may prepare but must not publish a public release, invite tester waves, or deploy release-critical changes without Max approval.
- PRs should clearly distinguish release prep from approved release action.

Verification:

- Release checklist requires Max approval before public release or tester expansion.
- Agents stop and ask when an action would publish, invite, merge/deploy release-critical work, or materially increase spend. "Materially increase spend" means any single action projected to consume ≥10% of the active LLM budget defined in D004, or any change that raises the per-user or global quota ceiling.

Spend approvals recorded under this gate:

- **2026-09-30: painted story-poster illustrations on the deployed beta.** Max approved turning on paid poster illustrations on the Fly beta as a proof of concept for a single user: `fly.toml [env] POSTER_IMAGES_ENABLED = "true"`, model `gpt-image-2.5-flare` at `medium`, `POSTER_DAILY_IMAGE_QUOTA` unchanged at 3 per player per rolling 24 h. The `config.py` default stays `false`. Each of the following needs a new Max decision: raising the quota, raising the quality, switching to a model with higher per-image cost, or letting more beta players paint. See `docs/decisions/0020-story-library-posters.md` ("Amendment 2026-09-30").
