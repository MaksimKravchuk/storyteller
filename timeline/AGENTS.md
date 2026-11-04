---
type: Component
title: Timeline
description: Game clock, scheduled events, time costs, and event effects.
resource: timeline/
tags: [timeline, events, game-clock]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `timeline/`.

# Boundary

`timeline/` owns game-clock advancement, scheduled events, time costs, and event
effects. It does not decide which events to schedule (the Director and
generators in [cast](/cast/AGENTS.md) do) and makes no LLM calls.

# Contents

- `event.py` — `GameEvent`, `EventEffect` (effect-type payload table in its
  docstring), `EventStatus`.
- `event_manager.py` — `EventManager`: `schedule`, `cancel`, `advance_time`,
  `get_pending_events`; `all_events` getter/setter for persistence.
- `effect_applier.py` — `EffectApplier` handler table per effect type.
- `effect_memory.py`, `effect_memory_slots.py` — witness memories written
  after an effect mutates NPC state.
- `time_costs.py` — `BASE_ACTION_COSTS`, `resolve_time_cost`.
- `_uuid_coerce.py` — `coerce_uuid` for JSON-roundtripped effect payloads.

# Local Rules

- Preserve deterministic behavior for event and time-cost logic.
- Prove changes with unit tests around the consumer that applies the event.
- This directory is in the mutation-testing scope.
- Keep `EffectApplier` silent on unknown effect types
  (`tests/test_effect_applier.py`); `SOCIAL_MEMORY` is applied by
  `cast/_npc_social_events.py`.

# Patterns

- New effect type: document its payload in the `EventEffect` docstring, add a
  handler to `EffectApplier._handlers`, and a slot builder in
  `effect_memory_slots.py` if witnesses should remember it.
- Narrow payload ids through `coerce_uuid`, as `_move_npc` and `_remove_npc`
  do.
- `apply` captures pre-state before the handler and emits memory after, so
  witness text can still name the NPC and origin.
- Lookup tables are `MappingProxyType` (`BASE_ACTION_COSTS`).

# Anti-patterns

- Mutating NPC location or popping the NPC before
  `preserve_departing_npc_memories`; memories lose their city anchor (comment
  in `_remove_npc`; `tests/test_effect_applier_memory_preservation.py`).
- Recomputing `completes_at` on rehydrated events; `_derive_completes_at` only
  fills it when the key is missing so DB rows round-trip.
- Moving a resident out of `Location.npcs_present` for anything but
  `MOVE_NPC` / `REMOVE_NPC`
  (`docs/decisions/0023-pin-scenes-to-persistent-places-and-anchor-npcs.md`).

# Related

- [Engine](/engine/AGENTS.md)
- [Models](/models/AGENTS.md)
- [Knowledge](/knowledge/AGENTS.md)
- [DB converters](/db/converters/AGENTS.md)
