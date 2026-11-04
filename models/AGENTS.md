---
type: Component
title: Models
description: Domain models for game state, settings, characters, NPC cards, scenes, locations, goals, and visible entities.
resource: models/
tags: [models, domain, pydantic]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `models/`.

# Boundary

`models/` owns Pydantic domain objects. Domain models stay separate from ORM
rows in [db](/db/AGENTS.md). No LLM calls, I/O, or agent logic here; behavior
on models is small, pure, and deterministic.

# Contents

- `base_model.py` — `StorytellerBase` with a validated `UUID4` `uuid`.
- `game_state.py` — `GameState`, `PlayerState`, clock and time-of-day labels.
- `character.py`, `npc_card.py` — characters and `NPCCard` (mood, hostility,
  goals, `values_vector`, player-visible name gating).
- `location.py`, `scene.py` — `Location` hierarchy, `Scene`, `SceneNPC`,
  `PointOfInterest`; `scene_action_log.py` — per-scene NPC short-term log.
- `goal.py` — `Goal`, `GoalKind`, `OffSceneOutcome`; `relationship.py` —
  directed `Relationship` with clamped intensity.
- `setting.py`, `world_state.py`, `values_vector.py`, `visible_entity.py`,
  `player_character_input.py` (onboarding DTO, not runtime state).

# Local Rules

- Adding a model field that a downstream consumer must read requires a
  consumer-side integration test.
- Coordinate persisted fields with [db converters](/db/converters/AGENTS.md).
- This directory is in the mutation-testing scope.
- Transient per-turn fields (for example `NPCCard.emotional_mood_floor`) must
  say so in a comment and stay out of the converters.

# Patterns

- Normalize LLM output at the model boundary with `mode="before"` validators:
  `Location._coerce_location_type`, `Relationship.coerce_kind`,
  `_coerce_points_of_interest` in `scene.py`.
- Player-visible NPC names come only from `NPCCard.known_names_for_player` /
  `label_for_player`.
- Alias lists keep "first element is primary" and reject empties via
  `clean_names` (`PointOfInterest`, `VisibleEntity`).
- Keep state-mutating helpers outside the class when WPS601 bites, as
  `_store_clock` in `game_state.py` does.

# Anti-patterns

- Storing freeform `location_type` text: it overflows the DB column and
  misroutes city-scoped rumor walks (comment in `location.py`).
- Reading a stranger's `name` directly for player-facing text; leaks
  un-introduced names
  (`docs/decisions/0007-gate-npc-departure-names-at-ticker-source.md`;
  `tests/test_watchman_regression.py`).
- Adding a field like `known_names_for_player` without wiring the prompt that
  reads it; the supplier test passed while the Narrator never saw it (root
  `CLAUDE.md` Testing section).
- Letting an LLM decide `Relationship.intensity` or the derived mood; those
  numbers are pure math
  (`docs/decisions/0011-deterministic-emotional-memory-subsystem.md`).

# Related

- [Cast schemas](/cast/schemas/AGENTS.md)
- [Knowledge](/knowledge/AGENTS.md)
- [Timeline](/timeline/AGENTS.md)
- [DB tests](/tests/db/AGENTS.md)
