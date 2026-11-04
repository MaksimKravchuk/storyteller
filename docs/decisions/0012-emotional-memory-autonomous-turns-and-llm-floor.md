---
type: Decision
title: "Emotional memory on autonomous NPC turns + LLM-proof mood floor"
status: stable
governs:
  - cast/npc_turn.py
  - cast/emotional_memory.py
  - cast/hostility.py
  - cast/_relationship_drift.py
  - knowledge/memory.py
  - cast/director_dialogue.py
  - models/npc_card.py
  - db/converters/npc.py
---
# ADR-0012: Emotional memory on autonomous NPC turns + LLM-proof mood floor

Date: 2026-06-20
Status: Accepted
Decision owner: Max
Related:
- ADR-0011 (`docs/decisions/0011-deterministic-emotional-memory-subsystem.md`) — the subsystem this extends; this record resolves its documented "Known limitation / follow-up" and tightens its mood-precedence rule. ADR-0011 remains accepted; nothing here reverses it.
- ADR-0002 (`docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`) — benchmark re-baseline / ratchet policy invoked by the consequences below.
- `cast/npc_turn.py`, `cast/emotional_memory.py`, `cast/hostility.py`, `cast/_relationship_drift.py`, `knowledge/memory.py`, `cast/director_dialogue.py`, `models/npc_card.py`

## Context

ADR-0011 shipped the deterministic emotional-memory subsystem but a Codex review of PR #309 surfaced four gaps where derived emotion did not actually reach the mechanic/prose it was built to drive:

1. **Autonomous turns ran on stale mood.** `apply_emotional_state` was invoked from exactly one production site — `DialogueHandler._execute_npc_dialogue` — so derivation only refreshed when the player *addressed* an NPC. On ordinary EXPLORE/WAIT/TALK-to-someone-else turns, `NPCTurnResolver` still fed the NPC's stale `current_mood` into the autonomous Actor prompt, so an NPC with fresh charged memories acted from a neutral mood until spoken to. ADR-0011 flagged this as an ADR-touching follow-up.

2. **The derived mood was erased mid-turn.** When an NPC had charged memories but `hostility_level == 0`, the derived mood was the *only* guard on `current_mood`. The subsequent `Actor.act` call could accept any lower `[MOOD:]` via `apply_llm_mood_update`, whose floor check considered only the mechanical hostility floor. An LLM emitting `[MOOD: calm]` overwrote the deterministic hostile mood before `RetaliationHandler` read it — so a memory-only grudge never fed retaliation.

3. **Neutral summaries drifted relationships.** A zero-charge dialogue-summary memory still carries a `subject_id`, so relationship drift folded it in with a zero contribution. That could materialize a spurious NEUTRAL relationship or relax a real RIVAL/ENEMY back toward neutral with no charged evidence behind it.

4. **Retaliation memories were emotionally inert.** `DialogueHandler.summarize_retaliations` persisted via `summarize_interactions_batch`, which stamped neutral charge. The new `RETALIATION` preset was never applied, so the subsystem ignored the very event (the NPC fighting back) that should build a grudge toward the player.

## Decision

Close all four gaps without changing the ADR-0011 data model or its no-LLM mandate.

1. **Derive emotional state once per NPC per autonomous turn.** `NPCTurnResolver._resolve_single_npc` calls `emotional_memory.apply_emotional_state(npc, graph, game_clock, turn=turn_count)` before building the turn prompt — mirroring the dialogue path so derivation is owned by the orchestrator, not the Actor. Derivation is pure and idempotent within a turn (mood is a function of memory state; drift re-targets to the stored intensity inside the hysteresis dead-band), so an NPC that is both addressed and resolves an autonomous turn deriving twice is harmless.

2. **Carry a transient emotional mood floor through the same-turn LLM update.** `NPCCard` gains a non-persisted `emotional_mood_floor: str | None`. `apply_emotional_state` sets it to the derived mood when there is live signal and clears it to `None` otherwise (so a fully-decayed grudge releases its grip). `apply_llm_mood_update` now floors against the **stronger** of the mechanical hostility floor and this emotional floor (`_effective_mood_floor`), so an LLM cannot de-escalate below a memory-derived hostile mood even at `hostility_level == 0`.

3. **Relationship drift ignores uncharged memories.** `_net_valence_by_subject` skips any memory whose original `charge_intensity == 0`. Genuinely charged memories still pass once decayed to zero, so a faded grudge can legitimately relax — but a never-charged chit-chat summary can neither create nor relax a relationship.

4. **Retaliation memories carry the felt charge.** The `DialoguePair` accepted by `summarize_interactions_batch` is widened to an optional 4-tuple `(npc_id, log, slots, charge)`; the charge defaults to neutral so plain dialogue summaries stay a scope boundary. `summarize_retaliations` passes `charge_presets.RETALIATION`, so the retaliator's persisted memory feeds mood derivation and relationship drift while still being LLM-summarised.

## Rationale

- **Orchestrator-owned derivation (decision 1)** keeps the ADR-0011 boundary intact: state mutation stays in the Director/turn-resolver layer next to `bump_hostility`, never inside the Actor. Per-turn-per-NPC derivation is the minimal generalization that makes a witnessed grudge visible on the *same* turn it lands, for NPCs the player never addresses.
- **A transient floor field (decision 2)** is the smallest carrier that survives the gap between derivation (turn start) and the LLM `[MOOD:]` update (mid-turn) without threading new arguments through the Actor. It is intentionally **not persisted**: it is re-derived every turn before it is read, so a DB column (and migration) would add cross-turn staleness risk for zero correctness gain. Taking the *stronger* of the two floors preserves ADR-0011's "emotion lifts, the mechanical floor never lowers" invariant while extending the same guarantee to memory-only grudges.
- **Skipping uncharged memories (decision 3)** restores the intended semantics: only felt experience moves a relationship. Keying on the *original* `charge_intensity` (not the decayed value) is what lets a real grudge relax to neutral while a neutral summary stays inert.
- **Widening `DialoguePair` (decision 4)** rather than adding a parameter avoids pushing `summarize_interactions_batch`/`_summarize_one` past their argument-count budget and keeps every existing 2-/3-tuple caller unchanged; the charge rides the per-pair tuple through the existing `_split_pair` normalization seam.

## Alternatives considered

### Alternative 1 (decision 1): a once-per-turn pass over all scene NPCs in the Director

Run a single derivation sweep over every scene NPC at the top of the turn. Rejected as heavier than needed: `_resolve_single_npc` already iterates exactly the eligible NPCs right before each prompt, so deriving there is the same coverage with no new traversal, and it co-locates derivation with the consumer (the prompt) it protects.

### Alternative 2 (decision 2): persist `emotional_mood_floor` as a DB column

Add a migration and round-trip the floor like `current_mood`. Rejected: the value is a within-turn guard, recomputed before every read; persisting it only invites stale-floor bugs across save/load and a needless schema change.

### Alternative 3 (decision 4): route retaliations through `MemoryEvent.create_memory_from_event`

`MemoryEvent` already carries charge fields. Rejected: that path stores the raw event text, dropping the LLM summary that `summarize_retaliations` deliberately produces (and that existing tests pin). Overriding the charge on the summariser path preserves the summary *and* stamps the felt charge.

## Consequences

Positive consequences:

- A witnessed or suffered grudge now reaches both the autonomous-turn prose and the retaliation mechanic on the same turn, for any NPC — not just the one the player is talking to.
- A memory-only hostile mood (hostility 0) can no longer be silently flattened by an inattentive Actor before retaliation reads it.
- Relationship drift reflects only charged experience; neutral chit-chat neither invents nor dissolves relationships.

Tradeoffs / risks:

- `benchmark npc_autonomy_*` baselines shift **deterministically**: NPCs now react to memory on autonomous turns. This is a defensible, reproducible re-baseline under ADR-0002 — record the new baselines, don't treat the shift as a regression.
- Per-turn derivation runs for every eligible scene NPC each turn. It is pure synchronous math over an NPC's own memory set, so the cost is bounded by memory count, but a very large scene pays it every turn.

What future agents must preserve:

- **Keep derivation orchestrator-owned** (dialogue path *and* `NPCTurnResolver`), never inside the Actor — same rule as ADR-0011.
- **`emotional_mood_floor` stays transient.** Do not add it to `db/converters/npc.py` or a migration; it is re-derived each turn. If you ever must persist it, clear it on load.
- **`apply_llm_mood_update` must floor against the stronger of the mechanical and emotional floors.** Reordering or dropping either floor re-opens the mid-turn-erasure gap.
- **Relationship drift keys on original `charge_intensity`**, not the decayed value — keep uncharged memories out of `_net_valence_by_subject` while letting charged-but-decayed ones through.
- **Dialogue summaries stay neutral by default**; only explicitly felt events (combat, retaliation) opt into a `ChargePreset`. The `DialoguePair` charge slot is opt-in.
- **`models/npc_card.py` is in the 95% mutation scope (ADR-0005).** The new field's default is mutation-covered by an explicit `is None` assertion; keep it.

## Verification / tests

- Relationship drift: a neutral (charge 0) summary neither materializes a relationship nor relaxes a standing ENEMY; a charged-but-decayed memory still relaxes (regression for gap 3).
- Mood floor: an emotional floor blocks an LLM downgrade at `hostility_level == 0`; still allows escalation above it; the effective floor is the stronger of mechanical and emotional (regression for gap 2). Consumer-seam: a memory-only grudge survives a same-turn LLM `calm`; a decayed grudge clears the floor.
- Autonomous turn: an un-addressed NPC with charged memories derives its mood before the turn prompt, and the derived label reaches the rendered prompt body (consumer-seam regression for gap 1).
- Retaliation charge: `summarize_retaliations` stamps the `RETALIATION` charge/valence/category and player `subject_id`; the stamped memory then drives negative relationship drift toward the player (regression for gap 4).
- `NPCCard.emotional_mood_floor` defaults to `None` (mutation cover).
- Full gauntlet green: `ruff`, `ruff format`, `flake8`, `mypy`, unit suite.
- Benchmark: re-run `npc_autonomy_*`; record deterministically shifted baselines per ADR-0002.

## Related files

- `cast/npc_turn.py` (`NPCTurnResolver._resolve_single_npc`)
- `cast/emotional_memory.py` (`apply_emotional_state` sets/clears the floor)
- `cast/hostility.py` (`apply_llm_mood_update`, `_effective_mood_floor`)
- `cast/_relationship_drift.py` (`_net_valence_by_subject`)
- `knowledge/memory.py` (`DialoguePair`, `_split_pair`, `_summarize_one`)
- `cast/director_dialogue.py` (`DialogueHandler.summarize_retaliations`)
- `models/npc_card.py` (`emotional_mood_floor`)
