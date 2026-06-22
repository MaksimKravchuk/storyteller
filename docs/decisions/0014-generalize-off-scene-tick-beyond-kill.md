# ADR-0014: Generalize the off-scene background tick beyond KILL-only

Date: 2026-06-22
Status: Accepted
Decision owner: Storyteller engineering
Related: GitHub issue #316, `cast/npc_background_tick.py`, `cast/_npc_offscreen_resolvers.py`, `models/goal.py`, `prompts/actor_prompts*.py`

## Context

The off-scene background ticker (`NPCBackgroundTicker`) advances NPC life
goals when the player isn't watching. Before this change it processed
exactly one of ten `GoalKind`s: `KILL`. Eligibility was hard-filtered
through a `GoalKind → ContestType` map that only contained
`{KILL: COMBAT}`, so PURSUE, ACQUIRE, PROTECT, EAT, ERRAND, REST, and the
social kinds were `return`-ed past before any resolution ran.

The result was a documented liveness gap (multi-agent debate, 2026-06-21):
nine of ten motivations were inert off-screen. The goal model already
carried `progress_notes` for every kind, but nothing produced or consumed
that state for non-KILL goals — rich state with no consumer is inert.

Constraints that mattered:

- The KILL combat path feeds the `npc_autonomy_*` benchmarks and must not
  regress — narration there has to stay byte-for-byte identical.
- Off-scene fan-out runs for every eligible NPC on every ≥1h advance, so
  any new work must stay deterministic and must not call an LLM.

## Decision

1. Replace the `GoalKind → ContestType` filter with a `GoalKind → resolver`
   dispatch table (`_RESOLVERS`). Eligibility is now "the goal kind has a
   registered resolver" instead of "the goal kind is KILL".
2. Add deterministic, no-LLM resolvers for `PURSUE`, `ACQUIRE`, and `REST`
   in `cast/_npc_offscreen_resolvers.py`. Each performs a pure-Python state
   step (track/secure/heal) and stamps a one-line `last_outcome` on the goal.
3. Add `last_outcome: OffSceneOutcome | None` to `models/goal.py` — a
   structured, locale-agnostic record (kind enum + `detail` slot), lighter
   than the `progress_notes` list and rendered per-locale at prompt time.
4. Surface `last_outcome` through a new **optional** Actor prompt section
   (`goal_outcome`, EN + RU) that renders only when the var is present.
5. Preserve the `KILL` path byte-for-byte: it keeps its original control
   flow and progress-note strings and never sets `last_outcome`, so its
   prompt body and benchmark narration are unchanged.

### Robustness follow-through (post-review hardening)

A review pass surfaced consumer-seam and reachability gaps; the decisions
that close them:

6. **Structured, locale-agnostic outcome.** The Actor prompt renders the
   `OffSceneOutcome` via per-locale template banks
   (`OFFSCREEN_OUTCOME_TEMPLATES` / `_RU`), so a Russian session never
   sees mixed-language outcome text. Progress-note audit lines stay
   English (matching the pre-existing note convention).
7. **Outcome read off `life_goal` directly.** `goal_outcome_var` reads the
   outcome independently of `select_active_goal`, so a just-completed goal
   (ACQUIRE/REST) or one masked by a promoted tactical goal still surfaces
   its outcome to the Actor.
8. **One-shot consumption.** The Actor clears `last_outcome` after the turn
   that rendered it, so a returning player sees the "while you were away…"
   reaction once, not on every subsequent turn.
9. **Liveness re-check + dead-target handling.** The ticker re-checks an
   actor's status before dispatching (a corpse killed earlier in the same
   tick runs no resolver); a PURSUE goal whose quarry was killed elsewhere
   is ABANDONED rather than pursued forever; REST matches free-form injury
   statuses by stem ("wounded left arm").
10. **Producer reachability.** ACQUIRE is added to the NPC-generator
    birth-goal pool and the Chronicler (a coherent standing material
    ambition). REST is added to the **Chronicler only** — a lifelong
    "rest" *birth* goal is incoherent, but a Chronicler-assigned reactive
    recovery directive is sensible — keeping the resolver reachable in
    normal play without polluting NPC generation. Both EN and RU producer
    prompts are updated in lockstep.

## Rationale

The off-scene loop — not the goal disposition data — was the binding
constraint on NPC liveness. The debate's counterfactual was decisive:
fixing the disposition while keeping the KILL-only filter leaves runtime
behaviour unchanged (the filter still drops everything else), whereas
fixing the loop lets NPCs make progress, so the world reacts to the passage
of time. Routing each kind through a resolver makes the loop extensible
without special-casing, and a dedicated `last_outcome` field gives the
Actor a cheap, single-sentence hook to react to off-scene developments on
re-entry — the missing consumer for the previously-inert state.

Keeping every resolver deterministic and LLM-free means widening
eligibility adds pure-Python work, not tokens, so the cost of "more NPCs
breathe" is negligible.

## Alternatives considered

### Alternative 1: Fix goal disposition, keep the KILL-only loop

Enrich the data NPCs carry but leave the eligibility filter. Rejected: the
filter still `return`s past non-KILL goals, so runtime delta ≈ zero. This
is the debate's losing branch.

### Alternative 2: Reuse `progress_notes` for the prompt instead of a new field

`progress_notes` is a bounded list tuned for retrospective history, not a
single prompt line. Surfacing the whole list per turn bloats the Actor
prompt and muddies "what just happened off-screen" with older entries. A
dedicated `last_outcome` is cheaper to render and easier to gate.

### Alternative 3: Fold `last_outcome` into the existing `goal` section

`PromptSection` is all-or-nothing on its `required_vars`: adding
`goal_last_outcome` to the existing `goal` section would drop the *entire*
goal block whenever the var is absent (i.e. for KILL), breaking the combat
prompt. A separate optional section keeps KILL byte-for-byte.

### Alternative 4: Give every remaining GoalKind a resolver now

PROTECT/EAT/ERRAND/social kinds have no obvious deterministic off-scene
semantics yet. Adding speculative resolvers would be unused complexity.
Eligibility keyed on the dispatch table means they remain skipped until a
resolver is intentionally added.

### Alternative 5: Store/stamp `last_outcome` as localized English prose

The first cut stored an English sentence. Rejected once RU sessions were
considered: the locale-agnostic ticker would bake English into the prompt
body, breaking locale parity (a CLAUDE.md hard rule). Passing the session
language into the ticker would also freeze the locale at write time. A
structured kind + `detail` rendered at the consumer keeps the prompt
single-language and the stored state locale-free.

### Alternative 6: Add REST to the NPC generator birth-goal pool

Rejected: a lifelong "rest" *birth* goal is incoherent and would have NPCs
spawn with a goal that completes on the first off-scene heal. REST reaches
the off-scene loop via the Chronicler (reactive recovery directive)
instead, which is the semantically right producer.

### Alternative 7: Copy `last_outcome` into the promoted tactical goal

To surface a PURSUE outcome after `promote_life_goals_on_sight` mirrors a
life goal into a tactical one, an option was to copy the outcome onto the
tactical goal. Rejected in favour of reading the outcome straight off
`life_goal` (decision 7): one read site, no duplication, and it also
covers the completed-goal case for free.

## Consequences

Positive consequences:
- PURSUE/ACQUIRE/REST goals now progress off-screen; ACQUIRE can complete
  and REST can heal a recoverable status, so returning NPCs reflect time.
- The Actor prompt receives `last_outcome` for non-KILL goals, closing the
  producer→consumer gap the debate flagged.
- Adding a new off-scene behaviour is now one dispatch-table entry plus a
  resolver, not a change to the eligibility predicate.

Tradeoffs / risks:
- **Cost fan-out:** every NPC with a resolvable, ACTIVE life goal is now
  eligible on each ≥1h advance. Mitigation: resolvers are deterministic and
  never call an LLM, so the worst case is O(eligible NPCs) of pure Python —
  no token cost.
- **KILL regression risk:** mitigated by preserving the path byte-for-byte
  (no `last_outcome`, identical strings/flow) and a consumer-seam test
  asserting KILL renders no `goal_outcome` section.

Positive consequences (robustness pass):
- ACQUIRE and REST are now reachable in normal play (ACQUIRE via generator
  + Chronicler, REST via Chronicler), so the resolvers are not dead code.
- Off-scene outcomes are localized, surface even for completed/tactical-
  masked goals, and are shown exactly once per re-entry.

What future agents must preserve:
- The KILL off-scene path must stay byte-for-byte (no `last_outcome`, same
  progress-note text) — it backs the `npc_autonomy_*` benchmarks.
- Off-scene resolvers must remain deterministic and LLM-free; the eligible
  set scales with NPC count.
- The `goal_outcome` Actor section must stay optional (rendered only when
  `goal_last_outcome` is set) and keep EN/RU parity.
- `OffSceneOutcome` must stay locale-agnostic; add a template to **both**
  `OFFSCREEN_OUTCOME_TEMPLATES` and `_RU` when introducing a new kind.
- Producer kind lists must stay EN/RU lockstep (guarded by
  `tests/test_prompt_localization.py::TestGoalVocabularyLocaleParity`).

## Verification / tests

- `tests/test_npc_background_tick.py`: resolver behaviour for KILL (still
  byte-identical, `last_outcome` stays `None`), PURSUE, ACQUIRE, REST, plus
  eligibility is no-longer-KILL-only and unresolved kinds stay skipped.
- `tests/test_actor_prompt.py::TestActorPromptOffSceneOutcome`: consumer
  seam — a non-KILL `last_outcome` reaches the rendered Actor prompt; a KILL
  goal renders no outcome section.
- `tests/test_goal_prompt_vars.py`: `goal_outcome_var` is gated on an
  outcome being present, renders localized (EN + RU), and survives goal
  completion.
- `tests/test_npc_background_tick.py`: dead-quarry PURSUE abandons,
  free-form REST status heals, and an actor killed mid-tick runs no
  resolver.
- `tests/test_actor_prompt.py::TestActorPromptOffSceneOutcome`: a non-KILL
  outcome reaches the prompt, renders in Russian for RU sessions, and KILL
  renders no outcome section.
- `tests/test_npc_generator_goals.py`: ACQUIRE is accepted as a generator
  life goal; REST stays rejected at generation.
- `tests/test_prompt_localization.py::TestGoalVocabularyLocaleParity`:
  generator/Chronicler kind literals match EN↔RU after adding ACQUIRE/REST.
- `tests/test_db_converters.py::test_goal_round_trip`: the structured
  `last_outcome` survives the domain→row→domain round-trip (Goal persists
  as a JSON blob, so no migration is required).
- `tests/prompts/test_consumer_seam_contract.py`: every Actor section,
  including `goal_outcome`, renders into the captured prompt (kwargs
  snapshotted pre-drive since the Actor consumes the outcome).
- KILL benchmark byte-identity is additionally checked by the
  `npc_autonomy_emergent_vendetta` / `npc_autonomy_murder_plot` scenarios in
  the PR benchmark workflow.

## Related files

- `cast/npc_background_tick.py`
- `cast/_npc_offscreen_resolvers.py`
- `models/goal.py`
- `cast/actor_config.py`
- `cast/actor.py`
- `cast/_npc_generator_goals.py`
- `prompts/actor_prompts.py`
- `prompts/actor_prompts_ru.py`
- `prompts/npc_generator_prompts.py`
- `prompts/npc_generator_prompts_ru.py`
- `prompts/chronicler_prompts.py`
- `prompts/chronicler_prompts_ru.py`
- `tests/test_npc_background_tick.py`
- `tests/test_actor_prompt.py`
- `tests/test_goal_prompt_vars.py`
- `tests/test_npc_generator_goals.py`
- `tests/test_prompt_localization.py`
- `tests/prompts/test_consumer_seam_contract.py`
