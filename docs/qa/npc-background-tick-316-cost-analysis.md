# NPC background tick #316 QA cost analysis

Copy-ready summary for PR/ADR:

Widening background eligibility from KILL-only to the resolver dispatch table makes every off-scene NPC with an ACTIVE LIFE goal whose `GoalKind` has a deterministic resolver eligible on each clock advance of >=1h. The cost is deterministic Python work, not token spend: `NPCBackgroundTicker.tick()` walks the NPC map once, builds the eligible list, then awaits at most one resolver step per eligible NPC. The new PURSUE, ACQUIRE, and REST resolvers do not instantiate performers, call `BaseLLMClient.send_message`, query providers, or run benchmark/e2e flows; they update bounded goal fields (`turns_pursued`, `progress_notes`, `last_outcome`, and sometimes `status`/`physical_status`).

Expected runtime shape:

- No-goal fast path: `any(npc.life_goal for npc in game_state.npcs.values())`, then return.
- Per >=1h advance with goal-bearing NPCs: O(total NPCs) eligibility scan + O(eligible NPCs) resolver work.
- Resolver fan-out bound: one resolver invocation per eligible NPC per tick, sequentially, so there is no async fan-out into parallel NPC actions.
- Token cost: zero for background ticking itself; tests poison `BaseLLMClient.send_message` and still tick PURSUE + ACQUIRE successfully.

Remaining fan-out risks:

- Large casts still pay the O(total NPCs) eligibility scan on every >=1h advance once at least one life goal exists.
- KILL remains the expensive deterministic path relative to the new resolvers because a co-located target can persist combat memory; this is still not an LLM call, but it can write knowledge/memory state.
- Future resolver additions must keep the one-step/no-LLM contract. Adding provider calls, knowledge graph broad searches, or nested NPC ticks inside a resolver would change this analysis.

KILL regression risk:

KILL is intentionally kept on the pre-existing contest path: co-located target -> combat roll -> predicted outcome -> memory persistence -> commit outcome -> progress note -> kill-goal completion. It still does not stamp `last_outcome`, and the wait-note text for no co-located target remains `offscreen wait (...): no co-located target`. QA coverage asserts both the lethal co-located path and the no-target progress path, including `last_outcome is None`, to protect the benchmark-sensitive behavior.

Non-paid benchmark comparison:

Paid benchmark/e2e runs were not executed. The pinned characterized baselines remain the comparison point:

- `npc_autonomy_murder_plot`: baseline mean 10.0/10 across 5 iterations; all deterministic elements pass 5/5, including clash occurred, outcome recorded, Marcus killed, and narration describes clash.
- `npc_autonomy_emergent_vendetta`: baseline mean 5.0/10 across 5 iterations; clash occurred 4/5, outcome recorded 4/5, narration describes clash 5/5, life-goal emergence 0/5.

The deterministic KILL-path tests exercise the same off-scene combat seam those scenarios depend on without making paid LLM calls. No baseline JSON files were changed by this QA work.
