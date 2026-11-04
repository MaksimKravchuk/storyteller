# ADR-0024: Off-screen social write-back uses directed relationships, not `hostility_level`

Date: 2026-11-04
Status: Accepted
Decision owner: Storyteller engineering
Related: GitHub issue #319, ADR-0011, ADR-0014, `cast/_npc_social_consequence.py`, `cast/_npc_outcome.py`, `cast/_relationship_drift.py`

## Context

Autonomous NPC actions (on-scene NPC turns and the off-scene background
ticker) only wrote `physical_status` / `current_mood` on their victim.
Scheduled `SOCIAL_MEMORY` effects wrote a memory and a follow-on goal but
never moved the relationship. An NPC wronged away from the player formed
no grudge it could act on. Issue #319 proposed bumping `hostility_level`.

`hostility_level` is player-directed: it feeds the mood floor and
`RetaliationHandler`, which retaliates **against the player**. Raising it
for NPC-vs-NPC harm would make a victim attack the player.

## Decision

1. One shared write-back, `apply_social_consequence(actor, target, kind, turn)`:
   `harm` steps the target's directed `Relationship` toward the actor by
   -2, `kindness` by +2 (`shift_relationship`, same clamp and kind bands
   as ADR-0011 drift; structural kinds stay frozen), then seeds the
   existing follow-on life goal (harm → KILL, kindness → HELP) unless an
   active life goal exists.
2. `commit_outcome` takes the actor and calls it with `harm` whenever the
   victim survives (wounded or intimidated). A killed victim gets nothing.
3. The `SOCIAL_MEMORY` effect path calls the same function.
4. `hostility_level` is **not** touched by NPC-vs-NPC events.

## Rationale

-2 lands exactly on the ENEMY band that opens the `npc_opportunity`
hostile window, so the grudge is actionable on the victim's next turn
without any new prompt section. Reusing the relationship model keeps the
grudge directed at the right NPC.

## Consequences

- A surviving victim with no active life goal now hunts its attacker, so
  NPC feuds can escalate both ways off-scene.
- Later `drift_relationships` reads may move the stamped intensity toward
  what the accumulated memory charge implies; drift stays authoritative.
- New benchmark `npc_autonomy_grudge_formed` scores the write-back.

## Future-agent guardrails

- Do not route NPC-vs-NPC harm into `hostility_level`; it means "toward the player".
- Keep the harm delta at or below -2, or the opportunity window stops opening.
