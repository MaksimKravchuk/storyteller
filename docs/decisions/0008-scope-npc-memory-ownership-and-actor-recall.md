---
type: Decision
title: "Scope NPC Memory Ownership And Actor Recall"
status: stable
governs:
  - knowledge/graph.py
  - knowledge/query.py
  - db/repo_saver.py
  - cast/actor_memory.py
  - prompts/actor_prompts.py
  - prompts/actor_prompts_ru.py
  - tests/test_actor_memory_relevance.py
  - tests/prompts/test_actor_memory_relevance.py
  - tests/prompts/test_consumer_seam_contract.py
  - tests/test_prompt_localization.py
  - knowledge/query_filters.py
  - db/converters/knowledge.py
  - cast/actor.py
---
# ADR-0008: Scope NPC Memory Ownership And Actor Recall

Date: 2026-05-31
Status: Accepted
Decision owner: Max
Related: `knowledge/graph.py`, `knowledge/query.py`, `db/repo_saver.py`, `cast/actor_memory.py`, `prompts/actor_prompts.py`, `prompts/actor_prompts_ru.py`, ADR-0002, ADR-0005

## Context

NPC memory in Storyteller is represented as knowledge graph nodes plus edges. Personal experience is held through `WITNESSED` edges from NPC actor UUIDs to `PERSONAL_EXPERIENCE` nodes, while propagated hearsay is represented as `HEARSAY` nodes with `TOLD_BY` provenance edges.

The previous persistence path saved only edges rooted at data-bearing knowledge nodes, so `WITNESSED` edges from data-less NPC actor roots were dropped on save. It also wrote empty edge metadata, which meant per-edge flags such as `propagated_on_departure` and hearsay `recipient_id` ownership were lost.

The previous query path treated `HEARSAY` as location-visible only. That leaked recipient-specific hearsay to later co-located NPCs. Actor prompts also received a broad salient personal-memory set, so unrelated high-salience memories could crowd out memories about the player or an active goal target.

## Decision

Persist all graph edges, including edges rooted at data-less actor nodes. Store edge metadata as all edge attributes except `edge_type`; keep `edge_type` in the `knowledge_edges.edge_type` column.

Treat `TOLD_BY` edge metadata `recipient_id` as the ownership contract for `HEARSAY` nodes:

- If a `HEARSAY` node has one or more `recipient_id` values, it is visible only to matching NPC-scoped queries.
- If a `HEARSAY` node has no `recipient_id`, it remains legacy location-visible.
- Generic/admin queries without an NPC identity remain unfiltered.

Actor prompts use a separate Actor-side memory selector:

- Dialogue recall prefers personal memories whose `subject_id` is the player UUID.
- Autonomous NPC turns also include memories about the active goal target UUID.
- Engine-supplied `memory_concept_tags` can add concept-tagged matches without adding an LLM classifier.
- Broad held-memory fallback is used only when scoped matches are empty.
- Memories are deduplicated by UUID and capped at five.
- Personal experiences are excluded from the Actor's general knowledge block so the memory section is the only personal-memory channel.

## Rationale

NPC memory is player-visible state. Losing actor-root edges or edge metadata across save/load makes NPCs forget events they witnessed and can repeat propagation work that should be idempotent. Hearsay ownership matters because one NPC being told a rumor should not silently make every co-located NPC know it.

Keeping ownership on `TOLD_BY` edge metadata avoids a graph shape migration: the existing `HEARSAY` node and `knowledge_edges.metadata_` column already encode the relationship. Preserving legacy unowned hearsay keeps old saves and generic admin inspection behavior intact.

Actor-side memory assembly keeps the public knowledge query APIs intact while moving prompt relevance decisions to the Actor consumer seam. Filtering personal experiences out of general knowledge prevents an unrelated fallback memory from still reaching the prompt through another section.

## Alternatives considered

### Store recipient ownership on HEARSAY nodes

This would make ownership easier to query from a single node, but it would add a new node-field persistence contract and likely require a migration. It also duplicates a relationship property that already belongs on the provenance edge.

### Create one shared location-visible HEARSAY node

This preserves the older behavior, but it leaks private rumor delivery to NPCs who were never told. It also prevents tests from proving that a specific recipient retained the rumor after save/load.

### Change public knowledge query APIs for relevance

Adding new public query entry points would spread Actor-specific prompt rules into the knowledge layer. Existing holder-scoped subject and concept retrieval already provide the needed primitives, so the Actor can assemble its own prompt memory set.

### Keep personal memories in general Actor knowledge

This would let unrelated high-salience memories reach the Actor prompt even when the new memory section correctly selected scoped memories. The prompt would still be noisy, and consumer-seam tests could pass the memory section while the full prompt remained wrong.

## Consequences

Positive consequences:

- NPC-held personal memories survive save/load.
- Hearsay delivered to one recipient no longer leaks to later co-located NPCs.
- Edge flags such as `propagated_on_departure` survive persistence.
- Actor prompts receive a smaller and more relevant memory set.
- Admin/generic graph inspection remains unfiltered.

Tradeoffs / risks:

- Edge metadata must remain JSONB-safe when saved.
- Multiple `TOLD_BY` edges on one `HEARSAY` node make ownership an edge-set question; any matching `recipient_id` grants visibility.
- Actor memory relevance now depends on producers setting `subject_id` and optional concept tags consistently.
- Narrative behavior changes are benchmark-relevant and require approved benchmark runs before release-sensitive merges.

What future agents must preserve:

- Do not save only data-node-rooted graph edges; actor UUID roots are valid edge sources.
- Do not duplicate `edge_type` inside `knowledge_edges.metadata_`.
- Do not make recipient-owned `HEARSAY` location-visible to NPC-scoped queries.
- Do not treat malformed `recipient_id` metadata as a match.
- Keep legacy unowned `HEARSAY` location-visible unless a migration explicitly converts old saves.
- Keep Actor personal memories out of the general knowledge prompt section.
- Keep EN/RU Actor memory prompt sections paired with the same `required_vars`.

## Verification / tests

- `tests/db/test_repo_saver.py::TestKnowledgeEdgePersistence`
- `tests/db/test_repo_loader.py::TestLoadKnowledgeGraph::test_actor_root_witnessed_edge_rebuilds_memory_index_after_reload`
- `tests/db/test_repo_loader.py::TestLoadKnowledgeGraph::test_told_by_metadata_preserves_recipient_visibility_after_reload`
- `tests/db/test_repo_admin.py::TestNPCDetail::test_returns_persisted_root_memory_edges`
- `tests/db/test_repo_admin.py::TestNPCDetail::test_admin_knowledge_graph_keeps_recipient_metadata_unfiltered`
- `tests/test_knowledge.py::TestRecipientOwnedHearsayVisibility`
- `tests/test_rumor_propagation.py::test_propagated_hearsay_does_not_leak_to_later_colocated_nonrecipient`
- `tests/test_actor_memory_relevance.py`
- `tests/prompts/test_actor_memory_relevance.py`
- `tests/prompts/test_consumer_seam_contract.py`
- `tests/test_prompt_localization.py`

## Related files

- `knowledge/graph.py`
- `knowledge/query.py`
- `knowledge/query_filters.py`
- `db/converters/knowledge.py`
- `db/repo_saver.py`
- `cast/actor.py`
- `cast/actor_memory.py`
- `prompts/actor_prompts.py`
- `prompts/actor_prompts_ru.py`
