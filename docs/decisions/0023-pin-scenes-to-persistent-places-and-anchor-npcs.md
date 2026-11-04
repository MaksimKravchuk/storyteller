---
type: Decision
title: "Pin scenes to persistent places and anchor NPCs to them"
status: draft
governs:
  - db/converters/location.py
  - tests/test_scene_place.py
  - tests/test_npc_place_persistence.py
  - tests/test_scene_builder_known_places.py
  - tests/test_npc_generator.py
  - benchmarks/scenarios/memory_return_visit
  - tests/test_benchmarks_memory_return_visit.py
  - tests/prompts/_consumer_seam_kwargs.py
  - cast/scene_place.py
  - cast/_place_registry.py
  - cast/_place_residents.py
  - cast/_place_seating.py
  - cast/_scene_location.py
  - cast/scene_builder.py
  - cast/schemas/scene_response.py
  - models/scene.py
  - cast/director_execution.py
  - cast/director_dialogue.py
  - cast/director.py
  - cast/npc_generator.py
  - knowledge/memory.py
  - prompts/scene_builder_prompts.py
  - prompts/scene_builder_prompts_ru.py
---
# ADR-0023: Pin scenes to persistent places and anchor NPCs to them

Date: 2026-10-25
Status: Proposed
Decision owner: Max (player-facing behavior; the merge needs Max's approval)
Related: [ADR-0008](0008-scope-npc-memory-ownership-and-actor-recall.md) (NPC memory ownership and Actor recall), [ADR-0007 departure gate](0007-gate-npc-departure-names-at-ticker-source.md) (NPC schedule and departures), [ADR-0014 off-scene tick](0014-generalize-off-scene-tick-beyond-kill.md), [ADR-0002 consumer-seam tests](0002-prompt-consumer-seam-contract-tests.md), branch `fix/npc-place-persistence`

## Context

Production bug report from 2026-10-25. In a Norse fishing settlement the player told Eira, a net-mender on the landing, his name and that he was looking for his brother. He walked up the village path and came back to the landing. Then he asked Eira what he had told her. She did not remember any of it.

Eira's memory was fine. The player was talking to a different NPC. The cause had three parts:

1. **Scenes were not tied to places.** On every MOVE or SLEEP the Scene Builder made up a free-text snake_case `location_id`. It did not see the places the story already had, so `coerce_scene_location_id` could not parse that id as a UUID and collapsed it to the all-zero sentinel `UNKNOWN_SCENE_LOCATION`. The "same" landing never matched a `Location`. The player's `location_id` stopped following them, and new places never got registered or linked.
2. **Every rebuild filled the scene with new people.** `npcs_present` came back as free-text roles ("net-mender woman"), and `init_scene_npcs` generated a fresh `NPCCard` for each one. The original Eira was still in `game_state.npcs` with all her memories, but nothing brought her back into the scene.
3. **Names were unique only within a scene.** `NPCGenerator` avoided only names already in the current scene, so the stranger could also be called Eira. Dialogue targeting goes by name, so the player's "Eira, do you remember me?" could reach either of them.

One more problem made recall weak even when the right NPC answered. The memory summariser prompt asked for "what did the NPC learn / impression of the player" in 1–2 sentences. It often dropped exactly the concrete facts (names, the brother, the boat) that a player later tests an NPC on.

## Decision

**Scenes are pinned to persistent `Location`s.**

- `SceneBuilder` gets a new `known_places` prompt section (EN and RU) that lists the story's places by short id. The short id is the first 8 hex characters of the place UUID, from `cast.scene_place.place_key`. The list holds at most 20 of the most recently added places and always includes the player's current place. Each line marks where the player is now and lists the people at that place right now.
- `SceneResponse` returns either one of those ids, or a new snake_case key plus a new `location_name` field. `resolve_scene_location_id` accepts the short key or the full UUID, case-insensitively. Anything else maps to `UNKNOWN_SCENE_LOCATION`, and `location_name` goes into the transient field `Scene.place_name`.
- `PlanExecutor._swap_in_scene` calls `scene_place.enter_scene` after it replaces the scene. If the scene's place is unknown:
  - On a MOVE or the first scene, the place is registered as a new `Location`. Its name is `place_name`, or else the first sentence of the description, or else "Unnamed place". It goes inside the origin when the origin is a city, district, region or country, and next to it otherwise.
  - On any other rebuild (for example SLEEP), the player stays at their current place.
- Then the origin and destination are linked both ways in `connected_locations`, and `player.location_id` moves to the scene's place.
- `persistent_world_changes` lines in the Scene Builder prompt now use the same short key.
- A MOVE skips the scene rebuild ("walk over to the guard") only when every target is an NPC in the *current scene*, matched by role, name or occupation (`scene_place.all_targets_in_scene`). Before, any NPC known anywhere in the story counted. "Walk back to Eira at the landing" from somewhere else then kept the player in the old scene, and Eira answered through the walls.

**NPCs are anchored to places.**

- A place's residents are its `Location.npcs_present`. An NPC is added when it is registered (`Director._register_new_npc`, using the scene's `location_id` set by `NPCGenerator`). It is removed when it dies or moves house (`REMOVE_NPC` / `MOVE_NPC` effects). An NPC that walks off on its own autonomous turn (`npc_turn` MOVE) only leaves the current scene. It keeps its home place and is back the next time the place is rebuilt and its schedule has it there. Before, that MOVE also struck the NPC from `npcs_present`, so a resident who followed the player up a path was gone from home for good.
- When the player arrives, `_place_seating.seat_residents` puts the residents who are there now at the head of `scene.npcs_present`, with their real UUIDs, before any new NPC is generated. "There now" means alive and on shift according to `cast.npc_ticker.get_schedule_for(occupation)` at the current `game_time`.
  - Residents the player has met come first.
  - At most 5 residents are seated.
- If a Scene Builder role re-describes a resident (the role contains their name, or shares a word of 4 or more letters with their occupation), that role is dropped, so the resident is not duplicated.
- The prompt tells the Scene Builder not to list residents in `npcs_present`.
- When the player calls someone by name (`DialogueHandler`) and that name matches a living resident of the place, the resident is brought into the scene. The schedule does not matter here, and no namesake is generated. A name that belongs to an NPC living elsewhere never spawns a new NPC under it.

**NPC names are unique across the whole story.** `NPCGenerator._taken_names` is now every named NPC in `game_state.npcs`, not just the current scene.

**The memory summariser keeps concrete facts.** The summary is now 1–3 sentences. It keeps every concrete fact: the player's own name, people, places, objects, dates, requests, offers and promises. Then it adds the NPC's impression of the player, written in the language of the conversation.

## Rationale

- **The bug was about identity, not memory.** ADR-0008 already makes sure an NPC's own memories reach their Actor prompt. That only helps if the player is talking to the same NPC again. Stable places plus anchored residents are the smallest change that makes "come back and talk to her again" reach the same `NPCCard`.
- **Places and NPCs are matched by the engine, not by text.** The Scene Builder picks a place from a closed list of ids, and the engine seats residents by UUID. Matching NPCs by names or roles from an LLM is exactly what failed. Short 8-hex keys are reliable for the model to copy, and they keep prompt cost low compared with full UUIDs.
- **The existing data model was enough.** `Location.npcs_present`, `connected_locations`, `parent_location_id` and the occupation schedule already existed and were already persisted by `db/converters/location.py`. There is no new table and no migration. `Scene.place_name` is only read in the turn the place is registered, so it is not persisted.
- **Rebuilds that are not travel should not create places.** SLEEP and similar rebuilds keep the player where they are. Otherwise an unmatched id would make a new place, and the player would wake up somewhere new.
- **Unique names across the story** close the remaining gap where name-based targeting could pick the wrong NPC, even when seating worked.
- **The summariser fix lets the recall actually show.** With the right NPC back in the scene, an impression-only summary still made her answer "I remember you vaguely". The facts the player tests on have to survive summarisation.

## Alternatives considered

### Match places by name or description similarity

Let the Scene Builder keep inventing free-text ids, then fuzzy-match them against `Location.name`. Rejected because LLM place names drift between turns ("the landing", "the harbour", "the shore by the nets"). That drift is the same failure that broke NPC identity. A closed list of ids is deterministic and easy to test.

### Ask the Scene Builder to list returning NPCs by name

Rejected. That keeps NPC identity in the LLM's free text, which is the exact failure mode here. The engine already knows who lives where and who is on shift.

### Look up existing NPCs by name or role when the scene fills up

Reuse an existing card whenever a generated role or name matches one. Rejected as the main mechanism, because roles are vague ("fisherman" matches many NPCs) and it would pull in NPCs from other places. It survives only in a narrow form: `_is_newcomer` drops a role that re-describes a resident who is already being seated, and `resident_named` resolves an explicitly named resident of *this* place.

### Show full UUIDs in the prompt

Rejected because full UUIDs cost more tokens and models copy them less reliably. The resolver still accepts a full UUID if the model returns one.

### Keep names unique only within a scene

Rejected, because that is what let a namesake Eira appear. The cost is noted below.

## Consequences

Positive consequences:

- Leaving a place and coming back puts the player at the same `Location` with the same residents, so NPC memory (ADR-0008) works across visits.
- Places form a graph as the player travels (`connected_locations`, `parent_location_id`), and `player.location_id` stays correct. Other code that reads `location.npcs_present` now sees real data more often: witness selection in `_npc_combat_memory`, `_npc_social_memory` and `director_events`, rumor scope, and the on-shift filter in `director_execution`.
- New NPCs can no longer share a name with an existing NPC.

Tradeoffs / risks:

- The Scene Builder system prompt gets longer: one line per known place (at most 20) and up to 5 residents per line.
- `_taken_names` grows with the cast, which adds one name per NPC to the NPC generator prompt. It is marked in the code as `shortcut:` and should be capped or ranked if long games make it too large.
- The Scene Builder may still pick the wrong known place, or invent a new key for a place it should have recognised. A wrong known id puts the player in the wrong place. A missed match creates a duplicate place on a MOVE.
- Dropping roles that re-describe residents uses a shared-word heuristic. A real newcomer whose role shares an occupation word with a resident, for example a second "fisherman", is dropped for that scene.
- Schedule gating means that a resident who is off shift at the current time of day is not seated. The player can still call them in by name.
- The summariser change affects every NPC conversation summary, not only this scenario. Summaries are a little longer (1–3 sentences, still capped by `_SUMMARY_MAX_TOKENS`).

What future agents must preserve:

- **NPC identity across scenes goes by UUID, never by LLM text.** Do not reintroduce a path where a scene rebuild fills a place's known people from free-text roles before seating its residents.
- **The Scene Builder picks a place from the known-places list.** Keep the `known_places` section and `location_name` in both EN and RU prompts. Keep `place_key` as the only format shown to the LLM, and keep `resolve_scene_location_id` accepting it.
- **"Walking over to someone" means they are in the current scene.** Do not widen the MOVE skip-rebuild check back to NPCs known anywhere in the story.
- **Only a MOVE or the first scene may create a `Location`.** Other rebuilds must not move the player to a new place they never travelled to.
- **Residents live in `Location.npcs_present`.** Add to it on registration and remove on death or moving house. An autonomous walk-off leaves the scene, not the home place. Do not add a second residency store.
- **NPC names stay unique across the story** unless a different, UUID-based disambiguation exists for every name-targeted path.
- **The summariser prompt must ask for concrete facts and the player's name.** Do not go back to an impression-only summary.

## Verification / tests

- `tests/test_scene_place.py`: place resolution and registration rules (MOVE vs non-travel, coarse vs fine parent, fallback names), two-way links with no self or duplicate links, seating order, dropping re-described roles, the dead and off-shift filter, met-first ordering and the cap, `resident_named`, and `format_known_places` (lines, the cap keeping the current place, the empty case).
- `tests/test_npc_place_persistence.py`: end-to-end through the Director. A resident comes back with the same identity, the returning NPC's prompt recalls the first conversation (a consumer-seam check), a new place becomes a connected location, a resident named as a dialogue target joins the scene, and walking back to an NPC who is not in the current scene travels instead of staying put.
- `tests/test_scene_builder_known_places.py`: a known short id resolves, a new key keeps the sentinel and the name, and the known-places text reaches the rendered system prompt in both EN and RU (a consumer-seam check).
- `tests/test_npc_generator.py`: names are unique across the story.
- `benchmarks/scenarios/memory_return_visit/` and `tests/test_benchmarks_memory_return_visit.py`: a replay of the production report. Deterministic elements check that the player is back at the landing and that the original Eira (seeded UUID), not a duplicate, is in the final scene. Evidence-LLM elements check that her reply recalls the player's name, the brother, the scarf and the boat.
- Prompt-consumer-seam kwargs fixture updated: `tests/prompts/_consumer_seam_kwargs.py`.

## Related files

- `cast/scene_place.py`: `place_key`, `resolve_scene_location_id`, `enter_scene`, `all_targets_in_scene`, `format_known_places`
- `cast/_place_registry.py`: registering new places and the links between places
- `cast/_place_residents.py`: residency, schedule gating, `resident_named`
- `cast/_place_seating.py`: seating residents and dropping duplicate roles
- `cast/_scene_location.py`: `UNKNOWN_SCENE_LOCATION` sentinel
- `cast/scene_builder.py`, `cast/schemas/scene_response.py`, `models/scene.py` (`place_name`)
- `cast/director_execution.py` (`_swap_in_scene`), `cast/director_dialogue.py`, `cast/director.py` (`_register_new_npc`)
- `cast/npc_generator.py` (`_taken_names`)
- `knowledge/memory.py` (summariser prompt)
- `prompts/scene_builder_prompts.py`, `prompts/scene_builder_prompts_ru.py`
- `db/converters/location.py` (already persists `npcs_present` and `connected_locations`)
