# ADR-0011: Deterministic Dwarf-Fortress-style emotional memory for NPCs

Date: 2026-06-19
Status: Accepted
Decision owner: Max
Related:
- ADR-0008 (`docs/decisions/0008-scope-npc-memory-ownership-and-actor-recall.md`) — NPC memory ownership / Actor recall seam this builds on
- ADR-0002 (`docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`) — benchmark re-baseline / ratchet policy invoked by the consequences below
- ADR-0010 (`docs/decisions/0010-language-neutral-player-action-contract.md`) — locale-parity discipline
- `knowledge/charge.py`, `cast/_mood_derivation.py`, `cast/_relationship_drift.py`, `cast/emotional_memory.py`, `cast/hostility.py`, `cast/director_dialogue.py`, `cast/_npc_combat_memory.py`
- Migration `alembic/versions/b2c3d4e5f6a7_add_emotional_charge_and_values_vector.py`

## Context

NPCs carried a flat free-text `current_mood` that was set ad hoc by the scene/LLM and decayed only implicitly, and a `Relationship` model whose intensity/kind never drifted at runtime. A `RelationshipDraft` shape existed but was never applied during play, so an NPC's felt relationship toward the player (or anyone) was effectively frozen at whatever it was seeded with. There was no mechanism by which accumulated experience — being attacked, witnessing violence — changed how an NPC felt or how it treated a subject over time.

The product mandate for this subsystem is explicitly **algorithmic / Dwarf-Fortress-style**: emotion and relationship change must be reproducible, inspectable, and free of LLM nondeterminism, so the same memory history always yields the same mood and the same relationship drift. This sits next to, not inside, the existing mechanical `hostility` ladder (`cast/hostility.py`) and the scope-filtered knowledge graph (ADR-0008).

## Decision

Add a **no-LLM, fully algorithmic emotional-memory subsystem**. No number in this subsystem is produced or judged by an LLM.

Data model:

- `KnowledgeNode` gains `valence` (signed `[-1, 1]`, values-neutral base feeling), `charge_intensity` (`[0, 1]`, pre-decay), and `charge_category` (a key into an axis-signature table; empty string = neutral).
- `NPCCard` gains a seven-axis `ValuesVector` (`law`, `kinship`, `honor`, `wealth`, `faith`, `valor`, `tradition`).

`knowledge/charge.py` holds the `ChargePreset` presets (COMBAT, RETALIATION, ROUTINE_DIALOGUE, NEUTRAL), the `AXIS_SIGNATURES` table, read-time lazy decay (`decayed_intensity`, reusing the linear recency shape of `knowledge.query._memory_score` with `RECENCY_TAU_HOURS = 72.0`, intensity-only, never flipping the sign of valence, keyed off the passed `game_clock`), and `values_adjusted_valence` (the per-witness colouring).

`cast/_mood_derivation.py` + `cast/_relationship_drift.py` do the math; `cast/emotional_memory.py` is the public facade (`apply_emotional_state`). The deriver:

1. Reads the NPC's **unfiltered** personal memories (`graph.personal_memories_for`, not the education/scope-filtered query path — an NPC's own traces are never invisible to its own feelings).
2. Derives a mood label by squashing the salience-weighted, decayed, values-coloured aggregate with `tanh` and mapping it onto a label that is a **key in `cast.hostility._MOOD_INTENSITY`**, so the same label feeds both the retaliation mechanic and the Actor prose prompt.
3. Drifts each `Relationship` intensity/kind toward every memory subject. The player is one subject among many.

Six load-bearing sub-decisions:

1. **No LLM decides any number.** Valence, intensity, decay, mood, and drift are pure synchronous math.
2. **Values applied per-witness at READ time** via the `charge_category` axis-signature dot product (clamped to `[-1, 1]`). One shared co-witnessed node yields a different *felt* valence per witness without storing per-witness copies on the node.
3. **Mood precedence:** the derived mood is the authoritative baseline for the turn — it overwrites the (possibly decayed) prior label — and is then raised to the hostility `mood_floor` as a lower bound. Emotion can lift mood above the floor but never below it. The later LLM `[MOOD:]` path stays floor-guarded last (`apply_llm_mood_update`). Derived mood is only written when `has_emotional_signal` is true, so a memory-less or fully-decayed NPC keeps its prior label instead of being flattened to neutral.
4. **Lazy read-time decay, no EventManager hook.** Decay is computed at read time against the passed `now`, mirroring `knowledge/query.py`.
5. **Intensity→kind bands with a 0.6 hysteresis dead-band.** Only affective kinds (NEUTRAL/FRIEND/ALLY/RIVAL/ENEMY) drift; structural kinds (KIN/SUBORDINATE/SUPERIOR) are frozen. ENEMY is reachable at intensity `<= -2` so the `npc_opportunity` retaliation window stays open. Intensity is clamped to `[-3, 3]`.
6. **Option A prompt wiring:** reuse the existing `current_mood` prompt variable — no new `PromptSection`, EN+RU parity intact (`prompts/actor_prompts.py` + `prompts/actor_prompts_ru.py`). A consumer-seam test asserts the derived mood reaches the rendered prompt body in **both** locales.

Orchestration: derivation is invoked from `DialogueHandler._execute_npc_dialogue` in `cast/director_dialogue.py` — the orchestrator owns state mutation, mirroring how the Director bumps hostility before dialogue — **not** inside the Actor. Combat memories now carry a COMBAT charge with `subject_id = attacker` (`cast/_npc_combat_memory.py`). Dialogue summaries are left neutral (scope boundary).

Persistence: migration `b2c3d4e5f6a7` adds three `knowledge_nodes` columns (`valence`, `charge_intensity`, `charge_category`) plus `npcs.values_vector`, with `server_default` backfilling neutral, so pre-existing rows contribute no emotional signal until new charged events arrive.

## Rationale

- The product differentiator here is a *believable, reproducible* simulation of how characters feel and how grudges form. Routing any of it through an LLM would make mood and relationship drift nondeterministic and unbenchmarkable, defeating the Dwarf-Fortress-style mandate.
- **Read-time per-witness valence** is the central efficiency win: a single co-witnessed event (a brawl in a tavern) is stored once, yet a law-valuing guard and a valor-valuing mercenary feel it differently because each one's `ValuesVector` dots against the event's axis signature at read time. Storing per-witness charge would multiply node count by the witness set and duplicate decay bookkeeping.
- **Reusing `current_mood` and `_MOOD_INTENSITY`** means the deterministic mood plugs into the *existing* retaliation mechanic and the *existing* Actor prompt with zero new wiring surface — the smallest possible change that makes derived emotion both mechanically and narratively visible. It also keeps the locale-parity surface unchanged (no new section to translate).
- **Mood floor as a lower bound** preserves the mechanical guarantee from `bump_hostility`: an NPC the player just attacked cannot be narrated as `content` because its memories happen to net mild. Emotion enriches above the floor; the floor protects the mechanic.
- **Lazy decay** mirrors the established `knowledge/query.py` recency model, so there is one decay mental model in the codebase rather than two, and no new EventManager side effect to reason about (EventManager side effects are a documented failure class).

## Alternatives considered

### Alternative 1: LLM-driven mood

Let an LLM read the memory set and emit a mood / relationship verdict. Rejected: nondeterministic, unbenchmarkable, and in direct conflict with the algorithmic mandate. The whole point is reproducibility.

### Alternative 2: Store per-witness charge or axis-signature on the node

Materialise each witness's felt valence (or a per-witness axis-signature) on the `KnowledgeNode` at write time. Rejected: read-time values application is leaner, respects the shared-node optimization (one stored node, N felt valences), and avoids per-witness write fan-out and the decay-bookkeeping duplication that per-witness storage forces.

### Alternative 3: EventManager-driven decay

Schedule a recurring EventManager effect that attenuates charge intensity on a clock tick. Rejected: lazy read-time decay mirrors the existing `query.py` recency shape, needs no scheduled event, and avoids adding an EventManager side effect (a documented regression class). Read-time decay is also self-correcting across save/load gaps because it is computed against the absolute game clock.

## Consequences

Positive consequences:

- NPC mood and relationships now change deterministically with lived experience; grudges form and (slowly) fade.
- One co-witnessed event yields per-witness emotional colour without per-witness storage.
- Derived emotion is both mechanically active (retaliation) and narratively visible (Actor prose) through one variable.
- Fully reproducible, so it is benchmarkable and unit-testable end to end.

Tradeoffs / risks:

- `benchmark npc_autonomy_*` baselines may shift **deterministically** as NPC mood/relationships now react to memory. This is a defensible, reproducible re-baseline under the benchmark ratchet policy (ADR-0002) — record the new baselines rather than treating the shift as a regression.
- Mood labels are coupled to `_MOOD_INTENSITY` keys: a label produced by the deriver that is not a key in that table scores 0 and the retaliation mechanic silently no-ops for that NPC.
- The `ValuesVector` adds a per-NPC tuning surface; mis-tuned axis signatures change felt valence globally.

What future agents must preserve:

- **Never route any of these numbers (valence, intensity, decay, mood, drift) through an LLM.** The subsystem's value is its determinism.
- **Keep EN/RU `current_mood` paired.** The derived mood reaches the prompt only via the existing `current_mood` variable in `prompts/actor_prompts.py` and `prompts/actor_prompts_ru.py`; editing one locale without the other breaks the consumer seam (ADR-0010 parity discipline).
- **Mood labels emitted by the deriver must stay keys in `cast.hostility._MOOD_INTENSITY`**, or retaliation silently no-ops. If you add a mood band, add the matching `_MOOD_INTENSITY` key.
- **Mood-floor precedence is load-bearing:** derived mood is the baseline, the hostility floor is a lower bound (emotion raises, never lowers below the floor), and the LLM `[MOOD:]` path stays floor-guarded last. Do not reorder these.
- **Keep decay lazy / read-time** and keyed off the passed game clock; do not add an EventManager hook.
- **Structural relationship kinds (KIN/SUBORDINATE/SUPERIOR) stay frozen**; only affective kinds drift. Keep ENEMY reachable at intensity `<= -2` so the `npc_opportunity` window stays open. Keep the 0.6 hysteresis dead-band so a decaying charge does not flap the kind read-to-read.
- **`models/`, `knowledge/`, and `db/converters/` changes here are in the 95% mutation scope** (ADR-0005). New deterministic code in those paths must be mutation-covered.
- Derive state from the **orchestrator** (`DialogueHandler`), not from inside the Actor, mirroring `bump_hostility`.

## Verification / tests

- Consumer-seam test: assert the derived mood reaches the rendered Actor prompt body in **both** EN and RU locales (the documented producer/consumer prompt-variable contract).
- Unit tests for `knowledge/charge.py`: decay never flips valence sign; decayed intensity hits zero past `RECENCY_TAU_HOURS`; `values_adjusted_valence` clamps and leaves neutral/unknown categories untouched; per-witness divergence on a shared node.
- Unit tests for `cast/_mood_derivation.py`: label bands; memory-less / fully-decayed NPC yields no signal (`has_emotional_signal` false) so the prior mood is preserved.
- Unit tests for `cast/_relationship_drift.py`: hysteresis dead-band; structural kinds frozen; ENEMY at intensity `<= -2`; player treated as one subject among many; intensity clamp.
- Mood-precedence tests in `cast/hostility.py`: `apply_derived_mood` raises to the floor and never undercuts it; LLM `[MOOD:]` stays floor-guarded.
- DB round-trip via `db/converters` for the three new `KnowledgeNode` fields and `NPCCard.values_vector`.
- Migration: `alembic upgrade head` against a scratch DB; confirm the four added columns and neutral server-default backfill.
- Combat seam: a combat memory carries a COMBAT charge with `subject_id = attacker`.
- Benchmark: re-run `npc_autonomy_*`; record deterministically shifted baselines per ADR-0002.

## Related files

- `knowledge/charge.py`
- `knowledge/node.py` (the three new fields)
- `cast/_mood_derivation.py`
- `cast/_relationship_drift.py`
- `cast/emotional_memory.py`
- `cast/hostility.py` (`apply_derived_mood`, `mood_floor`, `_MOOD_INTENSITY`)
- `cast/director_dialogue.py` (`DialogueHandler._execute_npc_dialogue`)
- `cast/_npc_combat_memory.py`
- `models/npc_card.py`, `models/values_vector.py`, `models/relationship.py`
- `prompts/actor_prompts.py`, `prompts/actor_prompts_ru.py`
- `db/converters/` (KnowledgeNode + NPCCard conversion)
- `alembic/versions/b2c3d4e5f6a7_add_emotional_charge_and_values_vector.py`
