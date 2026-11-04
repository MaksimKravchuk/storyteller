---
type: Component
title: Cast
description: Performer agents and turn orchestration code for Storyteller's theater runtime.
resource: cast/
tags: [cast, agents, runtime]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `cast/`.

# Boundary

`cast/` owns the Director and performer agents. Performer agents use the
`BasePerformer` pattern for LLM calls, structured JSON, context passing, and
call-chain logging. Prompt text belongs in `prompts/`, provider wire details in
`llm/`, and persistence in `db/`; `cast/` only consumes them.

# Contents

- `base_performer_class.py` — `BasePerformer`: `set_context`, `_send`,
  `_send_json` (strict schema first, prompt fallback), `_send_tool`;
  `_performer_retry.py` holds the JSON retry helpers.
- `director*.py` — Director split by concern: routing, execution
  (`PlanExecutor`), dialogue, events, hostility, witnesses, tools.
- Performers: `actor.py`, `narrator.py`, `scene_builder.py`,
  `npc_generator.py`, `data_miner.py`, `dramaturge.py`, `world_chronicler.py`,
  `item_generator.py`, `anachronism.py`.
- NPC autonomy: `npc_ticker.py`, `npc_turn.py`, `npc_background_tick.py`,
  `npc_goal_resolution.py`, `npc_opportunity.py` and the `_npc_*.py` helpers.
- Places and scenes: `scene_place.py`, `scene_swap.py`, `_place_*.py`,
  `scene_log*.py`, `visible_entities.py`.
- Deterministic helpers: `dice.py`, `emotional_memory.py`, `hostility.py`,
  `_reliability_metrics.py`; locale tables `narrator_labels.py` and
  `player_gesture_phrases.py`.
- `schemas/` — typed response payloads; see its own AGENTS.md.

# Local Rules

- Treat prompt-variable wiring and agent response schemas as consumer contracts.
- Prefer consumer-side tests that prove downstream prompts or runtime code
  receive the new value.
- Coordinate schema changes with [cast schemas](/cast/schemas/AGENTS.md) and
  prompt changes with [prompts](/prompts/AGENTS.md).
- Narrative-affecting behavior may require approved benchmark evidence.
- `dice.py` is in the mutation-testing scope (ADR-0005); keep it pure.

# Patterns

- New performer: subclass `BasePerformer`, pick the locale bundle in
  `__init__` (`get_narrator_prompts(language)` in `narrator.py`), feed vars via
  `set_context(...)`, implement async `act()`.
- Structured output: `_send_json(prompt, response_model=SceneResponse)` as in
  `scene_builder.py`; the strict path degrades on `NotImplementedError`.
- Player-visible NPC names go through `NPCCard.label_for_player`, as in
  `npc_ticker._departure_line` (ADR-0007 departure-names).
- Cold fallbacks call `record_fallback(agent, reason)` from
  `_reliability_metrics.py` (see `narrator.py`, `dramaturge.py`).
- Locale-dependent phrases live in `make_locale_lookup` tables
  (`narrator_labels.py`, `player_gesture_phrases.py`), never inline strings.
- Split modules that hit flake8 member/import budgets into underscore-private
  helper modules (`_performer_retry.py`, `_npc_*.py`).

# Anti-patterns

- Adding a `PromptSection` var without setting it in the consumer's
  `set_context`: the template skips it silently. Guarded by
  `tests/prompts/test_consumer_seam_contract.py`
  (`docs/decisions/0002-prompt-consumer-seam-contract-tests.md`).
- Composing English verb phrases for player actions; breaks Russian play
  (`docs/decisions/0010-language-neutral-player-action-contract.md`).
- Raising instead of degrading at cold fallback sites, or reworking them
  without data (`docs/decisions/0016-leave-cold-silent-fallbacks-unchanged.md`).
- Removing a resident from `Location.npcs_present` on an autonomous MOVE;
  residents left home for good (#373,
  `docs/decisions/0023-pin-scenes-to-persistent-places-and-anchor-npcs.md`).
- Streaming from a performer other than the Narrator, or streaming
  Dramaturge-reviewed drafts (`docs/decisions/0022-stream-narrator-prose-over-sse.md`).

# Related

- [Engine](/engine/AGENTS.md)
- [Knowledge](/knowledge/AGENTS.md)
- [Models](/models/AGENTS.md)
- [LLM](/llm/AGENTS.md)
- [Prompt tests](/tests/prompts/AGENTS.md)
