---
type: Decision
title: "Language-neutral structured player-action contract"
status: draft
governs:
  - interfaces/web/schemas.py
  - interfaces/web/player_gestures.py
  - cast/player_gesture_phrases.py
  - interfaces/web/service.py
  - interfaces/web/static
  - models/npc_card.py
  - prompts/locales.py
  - db
  - cast/narrator_labels.py
  - tests/test_web_schemas.py
  - tests/test_player_gestures.py
  - tests/test_web_api.py
  - interfaces/web
  - interfaces/web/runtime.py
  - interfaces/web/action_errors.py
---
# ADR-0010: Language-neutral structured player-action contract

Date: 2026-06-01
Status: Proposed
Decision owner: Max (release/product direction)
Amends: `docs/decisions/0006-player-dashboard-gui.md` (§6 informational-only map nodes; Alternative 4 "clickable map nodes that move the player")
Extended by: `docs/decisions/0019-player-ui-stage-visual-language.md` (entity hues keyed to the gesture `entity_kind`; `action_html` rendered as a stage cue; language-neutral location/daypart icons)
Related: `interfaces/web/schemas.py`, `interfaces/web/player_gestures.py`, `cast/player_gesture_phrases.py`, `interfaces/web/service.py`, `interfaces/web/static/`, `models/npc_card.py`, `prompts/locales.py`

## Context

ADR-0006 shipped the player dashboard with a Map / People / Inventory / Knowledge view and deliberately made map nodes **informational only** (§6): tapping a place did nothing. Its Alternative 4 ("clickable map nodes that move the player") was rejected for a specific, still-valid reason — the obvious implementation, emitting an English `"go to <place>"` action, **breaks non-English play**, and Russian is the primary play language. ADR-0006 closed with a guardrail: *"An English 'go to' verb is not an acceptable shortcut."*

A design handoff now reimagines the mobile play screen as a bottom-tab **Story / Character / Map** layout whose signature interaction is **tapping in-prose entities and map places to act**. Honoring that design without a language-neutral contract would reintroduce exactly the breakage ADR-0006 guarded against (a hardcoded `"talk to the vendor"` / `"go to the Temple of Saturn"`).

Two facts about the codebase shaped the contract:

- The narration already carries inline `<span class="poi" data-kind=… data-id=…>` spans (from `formatting.entity_markup.wrap_entities`), where `data-id` is the same opaque id the server emits: `str(uuid)` for NPCs/POIs, the `object_states` key for items, `str(uuid)` for locations.
- `game_state.last_visible_entities` is **not persisted** (it appears in no `db/` converter), so it is empty after `resume_session`. The persisted current scene (`npcs_present`, `points_of_interest`) and location (`object_states`) — plus the live map view — are the durable source for resolving what the player can currently act on.

## Decision

Add a **language-neutral structured player-action contract** and make in-prose entities and map nodes actionable through it.

1. **The client sends a gesture, never a phrase.** `POST /api/games/{id}/actions` accepts exactly one of free-text `{action}` (unchanged) or `{gesture: {intent, entity_kind, entity_id}}`, where `intent ∈ {examine, talk, move}` and `entity_kind ∈ {npc, poi, item, location}`. Allowed pairs: `talk→npc`, `move→location`, `examine→{npc,poi,item}`. The client transmits *what was tapped* (the server's own id) and *what it means* — no natural language.
2. **The server composes the action phrase in the session language.** `interfaces/web/player_gestures.compose_player_gesture` resolves the target's player-visible name and formats it with a locale phrase table (`cast/player_gesture_phrases.py`, EN + RU, mirroring `cast/narrator_labels.py`). The composed phrase ("поговорить с …", "пойти к …") then flows through the **existing, unchanged** turn pipeline (the LLM router already classifies EXAMINE/TALK/MOVE) — no new Director path.
3. **Targets resolve against persisted current state, not `last_visible_entities`.** NPCs via `current_scene.npcs_present`, POIs via `current_scene.points_of_interest`, items via the scene location's `object_states`, locations via the live `build_world_view(...).map` node set (current + connections + breadcrumb). An unknown/stale/no-longer-visible id raises `GestureResolutionError` → HTTP 422.
4. **NPC name-gating stays single-path.** The composed NPC name comes only from `NPCCard.label_for_player` (ADR-0006 §5), so a stranger's un-introduced name is never leaked into the phrase.
5. **`ActionResponse.action_html` carries the server-composed, HTML-escaped player line** so the client can render the player turn for a gesture (it never composed the phrase). Free-text turns also populate it; the client ignores it there because it already echoed the input optimistically.
6. **Russian + English only.** This is the project's full locale set (`prompts/locales.py`). Unsupported `<select>` languages degrade to English through the existing `resolve_locale` fallback — pre-existing behavior, unchanged.

This ADR is **Proposed**, not self-accepted: it amends a player-surface/release boundary that is Max's call (ADR-0004, ADR-0006).

## Rationale

- **A structured gesture is the only honest way to satisfy ADR-0006's guardrail.** Resolving the name and composing the verb server-side keeps the action in the session language by construction; the client never holds an English string. This *enables* the deferred Alternative 4 instead of taking the rejected shortcut.
- **Reusing the existing turn pipeline** means no new Director verb, no new classification path, and no new failure surface — a gesture is just a normally-composed action that happens to have been authored by a tap.
- **Resolving against persisted state** is correct after `resume_session` (where `last_visible_entities` is empty) and ties the gate to exactly what the scene/map currently expose.
- **Single name-gating path** preserves the ADR-0006 §5 invariant the codebase has regressed on before (a supplier method existing but a consumer re-deriving names and leaking identities).
- **`action_html` on the response** avoids a second round-trip and keeps the player line atomically consistent with the narration it accompanies (same discipline as `WorldView` riding the response in ADR-0006 §4).

## Alternatives considered

### Alternative 1: Client composes and sends the phrase
The tap builds `"talk to <name>"` and posts it as free text. Rejected: this is precisely the English-verb shortcut ADR-0006 forbids; it breaks Russian (and any non-English) play and re-derives names client-side, risking the name-leak regression.

### Alternative 2: A new Director "gesture" verb / movement endpoint
Add a dedicated movement/interaction contract in the engine. Rejected for this change: the LLM router already classifies a composed natural-language action into EXAMINE/TALK/MOVE, so a server-composed phrase needs no new engine surface. A bespoke verb would duplicate routing and widen the engine contract for no behavioral gain.

### Alternative 3: Resolve gesture targets from `last_visible_entities`
Match the tapped id against the per-turn visible-entity snapshot. Rejected: that field is not persisted and is empty after `resume_session`, so POI/item gestures would always fail post-resume. The persisted scene/location and the live map view are the durable source.

### Alternative 4: Keep map nodes informational (status quo of ADR-0006 §6)
Do nothing and leave travel to the text box. Rejected: the approved design's core is tap-to-act; with a language-neutral contract now in hand, the original reason for deferral no longer applies.

## Consequences

Positive:
- In-prose entities and map places become actionable in every supported language, with no English verb in the contract.
- No new engine/Director surface, no new endpoint, no extra round-trip.
- Name-gating remains correct by construction (one path through `label_for_player`).
- The PWA app shell is unchanged in *shape*: markup/logic/styles still live in the precached `index.html` / `app.js` / `style.css`; `PRECACHE_URLS` is untouched (only `CACHE_NAME` is bumped to evict the now id-coupled old shell), so D006 installability holds.

Tradeoffs / risks:
- A gesture is a real turn: its composed text is moderated, consumes turn quota, advances the clock, and `move` can change the scene. This is intended.
- Russian phrases inject the target name in the **nominative** form without pymorphy3 declension (e.g. "поговорить с стражник", not the declined "со стражником"). This is a documented v1 limitation that still satisfies the hard constraint (Russian output, no English verb), matching the imperfection the `narrator_labels` precedent already accepts.
- In-prose locations are not part of the `{npc,poi,item}` span taxonomy, so travel-by-tap is **map-only**; the text box remains the path for any place not shown on the map.

What future agents must preserve:
- Never let the client compose or send the action phrase for a gesture. The phrase is composed server-side in the session language; an English verb baked into the client or contract is not acceptable (this is the load-bearing reason the contract exists).
- Resolve gesture targets from persisted current state (scene/location/map), never from `last_visible_entities`.
- Keep all NPC naming for gestures routed through `NPCCard.label_for_player`; do not add a second name-resolution path.
- Keep EN/RU phrase tables paired in `cast/player_gesture_phrases.py`; add a real locale to `prompts/locales.py` before adding its phrases.
- Keep the play screen inside the existing precached shell files so `PRECACHE_URLS` stays unchanged and D006 installability holds.

## Verification / tests

- Contract shape: `tests/test_web_schemas.py` (ActionRequest XOR action/gesture; PlayerGesture intent×kind matrix; `ActionResponse.action_html`).
- Resolver: `tests/test_player_gestures.py` (each kind against persisted state; stranger gets descriptor not name; resolution independent of `last_visible_entities`; error paths raise `GestureResolutionError`).
- Locale parity: `tests/test_prompt_localization.py::TestGesturePhrases` (EN/RU distinct + English fallback).
- HTTP seam: `tests/test_web_api.py` (gesture body → `action_html` + character/world; invalid pair → 422; `GestureResolutionError` → 422; the play tab bar replaces the removed next-action chips).
- Standard gauntlet (ruff, format, flake8, mypy, pytest) plus the `interfaces/web/` boot demo per the Demo Contract.

## Related files

- `interfaces/web/schemas.py`
- `interfaces/web/player_gestures.py`
- `cast/player_gesture_phrases.py`
- `interfaces/web/service.py`
- `interfaces/web/runtime.py`
- `interfaces/web/action_errors.py`
- `interfaces/web/static/{index.html,app.js,style.css,sw.js}`
- `models/npc_card.py`
- `prompts/locales.py`
- `docs/decisions/0006-player-dashboard-gui.md`

## Amendment (2026-10-04): hostile NPC intents

Decision owner: Max. `intent` gains `attack` and `steal`, both valid only for `entity_kind = npc` (pairs `attack→npc`, `steal→npc`). Their EN/RU phrases live in `cast/player_gesture_phrases.py` beside the others ("attack {0}" / "напасть на {0}", "steal from {0}" / "обокрасть {0}") and flow through the unchanged turn pipeline — the Director already classifies combat and theft from free text. All guardrails above still apply; the v1 nominative-case limitation of the Russian phrases applies to these too. Verification: `tests/test_web_schemas.py` (new pairs accepted, `attack/steal→poi|item` rejected), `tests/test_player_gestures.py::test_npc_hostile_intents`.
