---
type: Component
title: Knowledge
description: NetworkX-backed world knowledge, rumors, hearsay, personal memories, and scoped query behavior.
resource: knowledge/
tags: [knowledge, graph, memory]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `knowledge/`.

# Boundary

`knowledge/` owns world facts, rumors, hearsay, scene summaries, and NPC-held
personal memories. Prompt text and agent decisions stay in
[cast](/cast/AGENTS.md); SQL rows stay in [db](/db/AGENTS.md).

# Contents

- `node.py` — `KnowledgeNode`, `KnowledgeScope`, `KnowledgeSource`,
  `CanonSource`, `EdgeType` (`WITNESSED`, `TOLD_BY`).
- `graph.py` — `KnowledgeGraph` over `nx.DiGraph` with a witness-memory index;
  `graph_serialization.py` — `to_dict` / `from_dict`.
- `query.py`, `query_filters.py` — `KnowledgeQueryEngine` scope, education,
  location and hearsay-ownership filters; salience+recency ranking.
- `memory.py` — `MemoryManager` (LLM summaries); `memory_dedup.py`,
  `memory_slots.py`, `salience.py`, `charge.py` (emotional presets, decay).
- `hearsay.py`, `rumor.py`, `rumor_scope.py`, `memory_preservation.py` —
  hearsay writes, city-scoped rumor spread, departing-NPC preservation.
- `scene_state.py` — persistent object deltas per location;
  `scene_consolidation.py`, `scene_summary_phase.py` — scene-end memory phases.

# Local Rules

- Preserve actor-root `WITNESSED` edges for personal memory.
- Preserve `TOLD_BY` edge metadata for recipient-owned hearsay.
- Keep graph serialization compatible with [db](/db/AGENTS.md) round trips.
- This directory is in the mutation-testing scope; follow the root mutation
  guidance for release-sensitive changes. `memory.py`,
  `scene_consolidation.py` and `scene_summary_phase.py` are LLM-driven and
  outside it.

# Patterns

- Use `salience.py` and `charge.py` presets at every `PERSONAL_EXPERIENCE`
  construction site instead of literals.
- Write hearsay only through `write_hearsay_node(graph, HearsayDraft(...))`.
- Register NPCs with `register_actor_node` (no `data` payload) so they are
  edge endpoints but invisible to queries.
- Mutate edges via `add_edge` / `remove_node` so the witness index stays in
  sync; after replacing `digraph`, call `rebuild_witness_memory_index` as
  `from_dict` does.
- Decay is lazy and read-time, keyed off the passed game clock
  (`decayed_intensity`, `_memory_score`).

# Anti-patterns

- Making `HEARSAY` with a `recipient_id` visible to other NPCs, or filtering
  admin queries without an NPC identity
  (`docs/decisions/0008-scope-npc-memory-ownership-and-actor-recall.md`;
  `tests/test_knowledge.py`).
- Reading an NPC's own memories through the scope-filtered query path for
  mood; use `personal_memories_for`
  (`docs/decisions/0011-deterministic-emotional-memory-subsystem.md`).
- Adding an EventManager decay hook or LLM-scored charge numbers (ADR-0011).
- Writing into `digraph` directly in production code; the witness index goes
  stale (`tests/test_knowledge.py` index tests).

# Related

- [Cast](/cast/AGENTS.md)
- [Models](/models/AGENTS.md)
- [DB converters](/db/converters/AGENTS.md)
- [Timeline](/timeline/AGENTS.md)
