# ADR-0006: Player dashboard GUI

Date: 2026-05-29
Status: Proposed
Decision owner: Max (release/product direction)
Amended by: `docs/decisions/0010-language-neutral-player-action-contract.md` (§6 and Alternative 4 — map nodes and in-prose entities become actionable via a language-neutral structured contract)
Extended by: `docs/decisions/0018-player-ui-stage-visual-language.md` (visual language — tokens, self-hosted fonts, semantic colour, `WorldView`-driven stage header; shell constraints unchanged)
Related: extends `docs/decisions/0004-retire-telegram-and-cli-player-clients.md` and `docs/studio/09-founder-decision-register.md` (D006 — PWA offline behavior); `interfaces/web/world.py`, `interfaces/web/world_schemas.py`, `interfaces/web/schemas.py`, `interfaces/web/static/`, `models/npc_card.py`

## Context

The player web UI was a two-column layout: a transcript of player input and narrator prose, plus a single Character sidebar (name, appearance, inventory, known NPCs, learned facts) built by `interfaces/web/character.py` / `character_schemas.py`. That surfaces the player's *own* state but gives no view of the world *around* the player — where they are, where they can go, who is in the scene with them, or what time it is in the game.

We wanted a richer dashboard GUI with four panels — Map, Inventory, Knowledge, and People & Time — without regressing the existing beta surface. Several constraints shaped the design:

- The web UI is the only supported player client (ADR-0004), so new player surfaces need an explicit product decision and consumer-side tests rather than incidental UI growth.
- The PWA must stay installable with gameplay online-required (founder-register D006); the service worker precaches a fixed app shell.
- The backend has no location coordinates — `Location` exposes `connected_locations`, `parent_location_id`, and a normalized `location_type` slug, but no x/y geometry — so a literal coordinate map is not buildable from current state.
- NPC names are gated per player: a stranger must not leak a name the player has not yet learned.
- Storyteller runs in multiple languages, so any player-facing affordance string baked into the engine contract risks breaking non-English play.

## Decision

Add a player dashboard GUI with Map, Inventory, Knowledge, and People & Time panels, under the following choices:

1. **Stay vanilla.** Extend the existing hand-written HTML/JS/CSS in `interfaces/web/static/` (`index.html`, `app.js`, `style.css`). No frontend framework, no bundler, no build step.
2. **Mobile-first layout.** On phones: a fixed bottom tab bar plus slide-up bottom-sheet panels. On desktop: a docked, tabbed side-rail as progressive enhancement. The phone layout is the baseline; desktop is the enhancement, not the reverse.
3. **Map is a connected-locations graph, not a coordinate map.** It renders the current location, its connected/known neighbours, and an ancestor breadcrumb (outermost first, e.g. Rome → Forum). It deliberately does *not* attempt spatial geometry, because the backend has no coordinates.
4. **New data rides a `WorldView` DTO on the existing payloads, not a separate endpoint.** `WorldView` (built by `interfaces/web/world.py`, mirroring `character.py`) is attached to both `GameSnapshot` and `ActionResponse`. Map / People / Clock are the only *new* data; Inventory and Knowledge continue to ride on the existing `CharacterInfo`. This keeps the world view per-turn-fresh and atomically consistent with the narration it accompanies.
5. **NPC name-gating routes only through `NPCCard.label_for_player`.** The People panel's `ScenePerson.label` is produced exclusively by `label_for_player(game_state, role_fallback)`; there is no second name-resolution path in the world builder.
6. **v1 map nodes are informational only.** Nodes display the world; they carry no movement affordance. The engine exposes no movement contract to bind a click to, and synthesizing an English "go to <place>" verb would break non-English play. Movement-from-map is explicitly deferred. *(Amended by ADR-0010: map nodes and in-prose entities are now actionable via a language-neutral structured `{intent, entity_kind, entity_id}` contract whose action phrase is composed server-side in the session language — the deferred affordance, without the English-verb shortcut this clause forbids.)*

This ADR is **Proposed**, not self-accepted: it extends the supported player surface and touches PWA/release posture, which are Max's call (ADR-0004, founder-register D006).

## Rationale

- **Vanilla** keeps the beta deployable as static files behind FastAPI with no toolchain, matching the existing web UI and avoiding a build pipeline the project does not otherwise have.
- **Mobile-first** matches the beta audience (friends on phones) and the PWA install story in D006; the side-rail is a non-regressing enhancement for desktop.
- **Connected-locations graph** is the only honest map the current data model can support. Faking coordinates would either invent geometry the engine never authored or require a backend change out of scope for a GUI task.
- **`WorldView` on the existing payloads** means the dashboard updates in lockstep with each turn's narration — no extra round-trip, no window where the map and the prose disagree. Mirroring `character.py` keeps the service layer thin and the panel shape next to its schema, and reuses the same defensive discipline (skip UUIDs that no longer resolve to a materialised location/card).
- **Single name-gating path** prevents the regression class ADR-0004 and `CLAUDE.md` warn about: a supplier method (`label_for_player`) existing but a consumer (the new People panel) re-deriving names and leaking un-introduced identities.
- **Informational-only nodes** avoid wiring a player-facing verb into the engine contract before a movement contract exists, and avoid the English-verb / non-English-play breakage.

## Alternatives considered

### Alternative 1: Introduce a frontend framework / build step

A framework (React/Svelte) with a bundler would make a four-panel responsive dashboard more ergonomic to author. Rejected: the web UI is intentionally framework-free static assets served by FastAPI; adding a build step is a disproportionate toolchain change for a beta GUI and contradicts the existing convention.

### Alternative 2: A separate `/api/games/{id}/world` endpoint

A dedicated world endpoint would isolate the new data. Rejected: it would let the map/people/clock drift out of sync with the turn's narration (separate fetch, separate timing) and add a polling/refresh concern. Riding `GameSnapshot` and `ActionResponse` keeps the world view atomically consistent and per-turn-fresh for free.

### Alternative 3: A coordinate / spatial map

A drawn map with positioned locations is the intuitive "map" a player expects. Rejected: the backend has no coordinates; any geometry would be fabricated client-side and could contradict the narrative graph. The connected-locations graph reflects exactly what the engine knows.

### Alternative 4: Clickable map nodes that move the player

Letting a player tap a neighbour to travel is the obvious next affordance. Rejected for v1: the engine exposes no movement contract for the UI to call, and the natural fallback — emitting an English "go to <place>" action — would break non-English sessions. Deferred until a language-neutral movement contract exists.

## Consequences

Positive consequences:
- Players get spatial, social, and temporal context (Map / People & Time) alongside their own state (Inventory / Knowledge), per turn, consistent with the narration.
- No new toolchain, no new endpoint, no new round-trip.
- Name-gating stays correct by construction — one path through `label_for_player`.
- The PWA app shell is unchanged: the dashboard ships inside the already-precached `style.css` / `app.js` / `index.html`, so `sw.js` and its `PRECACHE_URLS` need no edit, preserving D006 installability with no new offline-gameplay claim.

Tradeoffs / risks:
- The map is non-spatial; players expecting a drawn map may be surprised by a node/graph view.
- Map nodes are inert in v1 (no travel-by-tap), so movement still happens through the text action box.
- All new world data is computed every turn on both the snapshot and action paths; the builder must stay cheap and defensive (cycle/depth guards on the breadcrumb walk, skip-unresolved on connections and people).

What future agents must preserve:
- Keep Map / People / Clock on the `WorldView` DTO attached to `GameSnapshot` and `ActionResponse`; do not split them onto a separate endpoint or let them drift from the turn's narration.
- Route all People-panel naming through `NPCCard.label_for_player`; never add a second name-resolution path that could leak un-introduced NPC names.
- Do not add a coordinate map or a movement affordance to map nodes until the backend authors coordinates / a language-neutral movement contract, respectively. An English "go to" verb is not an acceptable shortcut.
- Keep the dashboard inside the existing precached app-shell files so `sw.js` / `PRECACHE_URLS` stay unchanged and D006 installability (online-required gameplay) holds.
- Stay vanilla — no framework or build step — unless a separate decision revisits the web UI's toolchain.

## Verification / tests

- `interfaces/web/world.py` builds `WorldView`; `interfaces/web/world_schemas.py` defines the DTO; `interfaces/web/schemas.py` attaches `world: WorldView` to both `GameSnapshot` and `ActionResponse`.
- Consumer-side coverage in `tests/test_web_world.py` (world builder) and `tests/test_web_schemas.py` (payload shape), plus `tests/test_web_api.py` for the snapshot/action seam.
- Name-gating asserted by checking `ScenePerson.label` comes from `NPCCard.label_for_player` (`models/npc_card.py:57`) — strangers do not surface un-introduced names.
- PWA invariant: `interfaces/web/static/sw.js` `PRECACHE_URLS` lists `/`, `/manifest.webmanifest`, `/static/style.css`, `/static/app.js`, and the two icons — unchanged by this work, since dashboard markup/logic/styles live inside the existing three precached shell files.
- Standard gauntlet (ruff, format, flake8, mypy, pytest) plus a boot-the-app screenshot demo per the Demo Contract for `interfaces/web/` changes.

## Related files

- `interfaces/web/world.py`
- `interfaces/web/world_schemas.py`
- `interfaces/web/schemas.py`
- `interfaces/web/character.py`
- `interfaces/web/static/index.html`
- `interfaces/web/static/app.js`
- `interfaces/web/static/style.css`
- `interfaces/web/static/sw.js`
- `models/npc_card.py`
- `tests/test_web_world.py`
- `tests/test_web_schemas.py`
- `docs/decisions/0004-retire-telegram-and-cli-player-clients.md`
- `docs/studio/09-founder-decision-register.md`
