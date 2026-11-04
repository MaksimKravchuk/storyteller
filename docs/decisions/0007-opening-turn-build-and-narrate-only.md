---
type: Decision
title: "Opening turn builds and narrates only — no NPC reactions"
status: stable
governs:
  - engine/game_engine.py
  - cast/director.py
  - cast/director_execution.py
  - cast/director_routing.py
  - tests/test_game_engine_lifecycle.py
---
# ADR-0007: Opening turn builds and narrates only — no NPC reactions

Date: 2026-05-30
Status: Accepted
Decision owner: Max
Related: `engine/game_engine.py`, `cast/director.py`, `cast/director_execution.py`, `cast/director_routing.py`

## Context

A new game is opened by `GameEngine.start_game`, which sends a synthetic, engine-authored prompt (`_OPENING_SCENE_PROMPT` — "Look around and describe the starting scene… include at least one named, addressable NPC…") through the Director exactly like a player action.

Because that synthetic prompt traversed the full player-action pipeline, the opening turn invoked an NPC's Actor agent **twice**:

1. **Dialogue path** — the LLM action router, nudged by the "named, addressable NPC" phrasing, classified the opening prompt as a TALK/targeted action. `_process_target_npcs` → `handle_dialogue` then fed the Actor `"Player is addressing you, <NPC>.\nPlayer action: Look around and describe the starting scene"` — incoherent, since the player addressed no one. The same router-produced target also triggered a second `init_scene_npcs` (an extra NPCGenerator call) for an NPC the player never referenced.
2. **Autonomous-turn path** — EXPLORE is a turn-counting action, so `_resolve_npc_turns` then ran every scene NPC's Actor a second time for an autonomous turn.

On turn zero the player has not acted and has addressed no one, so neither Actor call is justified. The double call wasted paid LLM calls on every new game and produced nonsensical NPC "responses" to the player merely looking around.

No prior ADR governs action routing or the opening turn, so there is nothing to supersede.

## Decision

The synthetic opening turn is treated as a distinct, deterministic mode that **builds and narrates the scene only** — no NPC dialogue, no NPC autonomous turns.

- `start_game` flags the turn: `director.execute(_OPENING_SCENE_PROMPT, context={"opening": True})`. Routing the opening through `execute()` (rather than a new public method) preserves call-chain tracking for the admin agent-flow graph.
- `Director.act` reads `context['opening']`. When set it **bypasses the LLM action router** and uses a fixed no-target `ExplorePlan` from `_build_opening_plan()`. A no-target EXPLORE with an empty `delegate_to` never enters the dialogue path (`should_talk` is false) and never generates a spurious target NPC, so the Actor is never fed the synthetic prompt as a player utterance.
- `PlanExecutor.execute_plan` gained a keyword-only `run_npc_turns: bool = True`. `act` passes `run_npc_turns=not is_opening`, so the opening skips `_resolve_npc_turns`. For every other turn the default `True` preserves existing behavior byte-for-byte.

Scene construction (`SceneBuilder` + `NPCGenerator` via `_prepare_scene`) still runs, so the opening narration can name on-stage NPCs and satisfy the opening prompt's social-affordance requirement — the named NPC is delivered by the scene description, not by a dialogue or autonomous-turn Actor call.

## Rationale

- The opening prompt is engine-authored, not player input. Sending it through the LLM router was the root cause: the router invented a TALK target from instructional phrasing. A fixed plan removes that non-determinism and the wasted router call.
- Splitting the two suppressions matches the two distinct failure modes: the no-target plan kills the dialogue path (and the spurious generator call) structurally; the `run_npc_turns` flag kills the autonomous-turn path explicitly.
- Suppressing the autonomous turn — rather than de-duplicating the NPC across the two paths — is the correct fix. De-duplication would have removed the *defensible* autonomous call and kept the *nonsensical* dialogue call. On turn zero neither is wanted.
- The `execute_plan` change is purely additive (a default-`True` flag), so the shared per-turn hot path is provably unchanged for normal play.

## Alternatives considered

### De-duplicate the NPC across dialogue + autonomous turns
Pass the dialogue NPC UUIDs as a skip-set into `_resolve_npc_turns`. Rejected: it keeps the nonsensical dialogue call (the actual bug), drops the defensible autonomous call, and changes every-turn behavior nobody complained about.

### Keep LLM routing on the opening, suppress paths with flags
Leave the router in place and gate both the dialogue path and `_resolve_npc_turns` with the opening flag. Rejected: it leaves the router free to produce spurious targets/NPCs and requires threading the flag through more call sites than the fixed-plan approach.

### A dedicated public `Director.open_scene()` method
Rejected: `cast/director.py` has no WPS214 (max-methods) headroom, and bypassing `execute()` would drop call-chain tracking for the opening turn's child agents. The `context={"opening": True}` flag through `execute()` is smaller and preserves tracking.

## Consequences

Positive:
- One fewer router LLM call and N fewer Actor calls per new game; no nonsensical NPC reply to "look around".
- The opening is deterministic — no flaky router classification of the synthetic prompt.
- Normal turns are untouched (additive flag, default `True`).

Tradeoffs / risks:
- NPCs are now silent and still on the very first frame; the living world begins on the player's first real action. This is the intended product behavior for turn zero.
- `_OPENING_SCENE_INTENT` is hardcoded English (it feeds the Narrator's turn intent). This matches the existing English-only `_OPENING_SCENE_PROMPT` precedent and is not a new locale regression.

What future agents must preserve:
- Do **not** re-enable LLM action routing for the opening turn, and do **not** run NPC dialogue or autonomous turns on it. The opening builds and narrates only.
- Keep `run_npc_turns` defaulting to `True`; it is an opening-only escape hatch, not a general toggle.
- If the opening needs richer behavior, add it to the build/narrate path — do not route the synthetic prompt as a player action.

## Verification / tests

- `tests/test_director_opening.py::test_opening_turn_does_not_invoke_npc_actors` — drives the real `Director.act` opening path; asserts `handle_dialogue` and `resolve_npc_turns` are never awaited, the router is bypassed, and the scene is still built and narrated. Fails on the pre-fix tree with "Awaited 1 times" (autonomous-turn path), passes after.
- `tests/test_director_opening.py::test_normal_turn_still_runs_npc_turns` — locks the suppression to turn zero: a non-opening turn still routes and still runs NPC autonomous turns.
- `tests/test_game_engine_lifecycle.py` — `start_game` wiring and the synthetic-prompt-hiding snapshot continue to pass with the `context={"opening": True}` flag.

## Related files

- `engine/game_engine.py` — opening turn flagged via `context={"opening": True}`.
- `cast/director.py` — `_build_opening_plan()`, `_OPENING_SCENE_INTENT`, opening branch in `act`.
- `cast/director_execution.py` — `run_npc_turns` flag on `execute_plan`.
