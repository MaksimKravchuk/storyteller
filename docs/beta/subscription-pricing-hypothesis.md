# Subscription pricing hypothesis for #245

Status: issue-ready planning brief; not a billing implementation plan.

Issue: [#245 — Draft subscription pricing hypothesis from beta telemetry](https://github.com/MaksimKravchuk/storyteller/issues/245)

## Executive summary

Storyteller is not ready to choose paid subscription pricing from measured beta economics yet. The current repository has the telemetry seams needed to produce a beta cost report, but this planning run found no accessible Wave 1/Wave 2 database export, no local cost rows, and no computed cost per started game or cost per 20-turn session.

Use the tiers below as validation hypotheses, not as a Stripe build spec:

| Tier | Price | Included monthly quota | Placeholder variable cost | Placeholder gross margin |
| --- | ---: | --- | ---: | ---: |
| Explorer | $9/mo | 100 successful player turns, 5 started games, 3 active games | $2.25 | 75.0% |
| Adventurer | $19/mo | 250 successful player turns, 10 started games, 5 active games | $5.50 | 71.1% |

The leading recommendation is to validate Explorer and Adventurer manually after real beta usage is exported. Do not launch a heavier paid tier or paid overages until measured cost/session, repeat usage, and qualitative feedback support longer sessions.

## Cost summary

Current cost numbers for #245:

- Cost per started game: not computable from accessible data.
- Cost per 20-turn session: not computable from accessible data.
- Accessible sample size: 0 beta games, 0 beta turns, 0 cost rows.
- Date range: none; no live or exported Wave 1/Wave 2 rows were available in this run.
- Provider/model mix: no observed beta mix available.

Available telemetry/reporting seams:

- `ai_call_logs` is the canonical spend source and records `session_id`, `turn_number`, `user_id`, `game_state_id`, `model`, token counts, and `created_at`.
- `AILogStore.usage_summary(...)` aggregates usage by user/session/game/day/model.
- `GET /api/admin/beta/cost-summary` returns prompt-free JSON totals, by-user rows, by-model rows, report rows, currency, and UTC date basis.
- Pricing defaults currently cover `gpt-5.4-mini` and `gpt-5.4-nano`; other observed model IDs need `MODEL_PRICING_JSON` or they will be flagged as unpriced.

Formulas to run once a real beta export exists:

- `cost_per_started_game = sum(call_cost where turn_number is null) / count(distinct session_id where turn_number is null)`
- `cost_per_20_turn_session = (sum(call_cost where turn_number is not null) / count(distinct session_id + ':' + turn_number where turn_number is not null)) * 20`
- Include `min(created_at)..max(created_at)`, active users, started games, successful turns, model breakdown, unpriced call count, and missing-token count with any pricing update.

## Retention and usage summary

Current retention/usage confidence is low for pricing, medium for diagnosing risk.

Observed/available signals:

- No real Wave 1/Wave 2 retention export was available during the planning run.
- Pre-beta QA evidence showed some playable sessions around 6 API turns, but not reliable 20-turn completion.
- The strongest current risk signals are start/action reliability, unclear NPC affordances, continuity drift, static-world loops, and clarification/repair turns.
- Existing plans call for report fields that #245 needs before a real pricing decision: median/mean turns per active user, returning users on another UTC day, and feedback count by category.

Pricing caveat: a turn quota that looks economically safe can still feel punitive if early turns are spent repairing ambiguity or NPC affordance failures. Validate perceived value and session depth before treating monthly turn caps as product-ready packaging.

## Proposed tier hypotheses

### Tier A — Explorer

- Price: $9/month.
- Intended segment: casual players who want a few short interactive stories per month.
- Included quota: 100 successful player turns/month, up to 5 started games/month, up to 3 active games at a time.
- Placeholder economics:
  - Planning cost assumption: $0.40 per 20 successful player turns and $0.05 per started game.
  - Turn cost: 100 / 20 * $0.40 = $2.00.
  - Start overhead: 5 * $0.05 = $0.25.
  - Estimated variable cost: $2.25/month.
  - Full-quota gross margin: 75.0%.
- Guardrail: keep full-quota measured variable cost at or below about $2.70/month for a 70% margin at $9.
- Validation question: do casual users see enough value before 100 turns, or do quality/repair turns make the cap feel too tight?

### Tier B — Adventurer

- Price: $19/month.
- Intended segment: engaged players who want ongoing stories, multiple settings, and enough quota for weekly play.
- Included quota: 250 successful player turns/month, up to 10 started games/month, up to 5 active games at a time.
- Placeholder economics:
  - Planning cost assumption: $0.40 per 20 successful player turns and $0.05 per started game.
  - Turn cost: 250 / 20 * $0.40 = $5.00.
  - Start overhead: 10 * $0.05 = $0.50.
  - Estimated variable cost: $5.50/month.
  - Full-quota gross margin: 71.1%.
- Guardrail: keep full-quota measured variable cost at or below about $5.70/month for a 70% margin at $19.
- Validation question: do heavier players show repeat-day retention and positive feedback, or does useful monthly play plateau below 250 turns?

### Optional later tier — Founder / Power Player

Do not launch this in the first paid experiment unless real beta telemetry shows low per-turn cost and strong repeat usage.

- Candidate price: $29/month.
- Candidate quota: 500 successful player turns/month, up to 15 started games/month, up to 8 active games at a time.
- Placeholder economics: $10.75/month variable cost and 62.9% gross margin at full quota.
- Risk: heavy users are exactly where narrative quality issues, clarification loops, and runaway model spend matter most.

## Deferred Stripe section

Stripe implementation remains deferred until Max explicitly approves changing founder decision D005.

Do not build in this scope:

- Stripe Checkout.
- Customer portal.
- Payment webhooks.
- Tax/VAT policy.
- Paid overage billing.
- Runtime payment routes or Stripe dependencies.

Allowed current scope is subscription-readiness planning: plan/entitlement seams, quotas, telemetry, admin reports, and a pricing hypothesis to revisit after measured beta cost/session and retention data exists.

## Validation gate before billing work

Before any billing implementation, produce a real beta report covering Wave 1 and preferably Wave 2 with:

- active users, started games, successful player turns, and date range;
- games reaching 5, 10, and 20 successful turns;
- users returning on another UTC day;
- mean/median turns per active user and distribution by user;
- cost per started game and cost per 20-turn-equivalent session;
- model mix, missing-token rows, and unpriced call counts;
- feedback counts by category and by turn bucket.

If measured full-quota margin for Explorer or Adventurer falls below 70%, reduce included turns, raise price, improve model routing/cost, or keep Storyteller in free beta until cost and quality improve.

## Source and caveat notes

Sources used:

- GitHub issue #245 acceptance criteria.
- `docs/plans/friends-beta-cost-quotas-feedback.md` work package 6.
- `docs/studio/09-founder-decision-register.md` D003, D004, and D005.
- `db/repo_ai_logs.py` usage aggregation and turn-count behavior.
- `costs/reports.py` cost summary payload construction.
- `interfaces/admin_reports.py` admin beta cost summary endpoint.
- Parent Kanban handoffs for cost, retention/usage, and tier hypotheses.

Caveats:

- The $0.40 per 20-turn session and $0.05 per started game values are placeholders for planning math only, not measured COGS.
- Start generation and player turns should be reported separately because `turn_number is null` represents start generation while numbered turns represent player actions.
- Missing token usage or unpriced model IDs can understate spend if not surfaced.
- Benchmark artifacts are not beta usage evidence.
- Pricing also depends on willingness to pay and product quality, not only gross margin.
