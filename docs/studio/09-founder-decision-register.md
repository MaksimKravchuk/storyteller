# Founder Decision Register

Release target: Friends Beta v0.2  
Owner: Max  
Studio operator: Hermes

This file records founder/game-design/product decisions that agents must not invent silently. Hermes may recommend defaults and continue execution when the default is low-risk, but items marked **Max decision required** block release until Max confirms them.

## Decision states

- **Chosen** — current operating decision.
- **Defaulted** — Hermes is proceeding with this default; Max can override.
- **Max decision required** — do not ship/release this item until Max decides.
- **Deferred** — explicitly out of current milestone.

## D001 — Beta release target

Status: **Chosen**

Decision: Target **Friends Beta v0.2** before any broad public launch.

Rationale:

- The product needs real friend/player feedback before paid acquisition or subscriptions.
- Invite-only access gives cost control while the AI gameplay loop is still being hardened.
- The milestone can validate PWA installability, accounts, persistence, cost telemetry, quotas, and feedback loops.

## D002 — Auth provider

Status: **Defaulted**

Decision: Use **Supabase Auth** for Friends Beta unless Max overrides before implementation starts.

Rationale:

- Fast beta path for email/social auth without owning password-reset/security workflows.
- Production-ish session model and account lifecycle.
- Avoids turning the beta milestone into a custom auth/security project.

Implementation constraints:

- Store only Supabase user identifiers and profile/account metadata needed by Storyteller.
- Keep all Supabase URLs/keys in environment variables; never commit secrets.
- Gate beta play behind invited/allowlisted accounts.

Max can override to Clerk, Google OAuth-only, or temporary invite-code accounts.

## D003 — Beta audience size

Status: **Defaulted**

Decision: Roll out in waves.

- Wave 1: 5 invited testers.
- Wave 2: 10–15 testers after cost/error review.
- Wave 3: 25–30 testers only after quotas and telemetry look safe.

Release blocker:

- Do not invite Wave 2+ until Wave 1 has at least one reviewed cost/error report.

## D004 — Cost budget

Status: **Defaulted**

Decision:

- Initial global beta LLM budget: **$50**.
- Per-user daily quota: **20 turns**.
- Per-user weekly quota: **50 turns**.
- Max active games per user: **3**.
- Public/guest play remains limited or disabled until cost telemetry is verified.

Rationale:

- Existing `ai_call_logs` already records token counts, so beta work should convert this into per-user cost telemetry and enforceable quotas.
- The app should fail closed with friendly quota/provider messages, not silent runaway spend.

Max decision required before release:

- Confirm or adjust the $50 initial budget.

## D005 — Subscription timing

Status: **Chosen**

Decision: Do **not** build Stripe subscriptions before Friends Beta.

Build now:

- Account plans/entitlements.
- Quotas.
- Cost telemetry.
- Admin reports.

Defer:

- Stripe Checkout.
- Customer portal.
- Payment webhooks.
- Tax/VAT policy.

Rationale:

- Pricing should be based on actual beta cost/session and retention.
- Premature billing adds operational and support burden before product-market feedback.

## D006 — PWA offline behavior

Status: **Chosen**

Decision: PWA should be installable, but gameplay is **online-required**.

Acceptance:

- Installed app shell opens.
- Offline state says Storyteller needs internet/model access to continue.
- Do not claim offline gameplay.

## D007 — Data/privacy posture

Status: **Defaulted**

Decision: Friends Beta privacy notice must say:

- Story prompts, player actions, generated narration, feedback, and account identifiers may be stored.
- AI requests are sent to model providers.
- Logs may be reviewed by Max/Hermes for debugging, product quality, and safety.
- Testers should not enter sensitive personal data.
- Testers can ask for deletion of their account/game data.

Max decision required before release:

- Confirm the public contact channel/email for privacy/deletion requests.

## D008 — Feedback channel

Status: **Defaulted**

Decision: Add in-app feedback first; optionally mirror/triage to GitHub or a private chat later.

Required feedback payload:

- user id/email
- game id
- turn number if available
- category
- free text
- timestamp

## D009 — Game design: beta success criteria

Status: **Max decision required**

Max should define or approve the subjective bar for a successful beta session.

Hermes default proposal:

- A new tester can install/open the app, sign in, start a story, play 10 turns, interact with at least one NPC, and submit feedback without help.
- At least 60% of Wave 1 testers complete one 10-turn session.
- At least 3 testers say they want to play another session.
- No P0 crashes or cross-user data leaks.
- Average model cost per 20-turn session stays under the budget model used for subscription planning.

## D010 — Release approval

Status: **Chosen**

Decision: Max remains final approver.

Agents may prepare PRs, release candidates, docs, deploy procedures, and private staging checks. Agents must not publish/invite testers beyond approved scope or merge/deploy release-critical changes without Max approval.
