# ADR-0019: Player web UI visual language — "the stage"

Date: 2026-09-30
Status: Proposed
Decision owner: Max (player-facing product direction)
Decision type: Product (player-facing UX / visual identity) + Architecture (web static assets, PWA app shell)
Extends: `docs/decisions/0006-player-dashboard-gui.md` (vanilla, mobile-first, `WorldView`, precached shell) and `docs/decisions/0010-language-neutral-player-action-contract.md` (tap-to-act entities, `action_html`, no English in the player contract)
Related: founder-register D006 (PWA online-required) and D007 (privacy posture) in `docs/studio/09-founder-decision-register.md`; `interfaces/web/static/{style.css,app.js,index.html,sw.js,manifest.webmanifest}`, `interfaces/web/static/fonts/`, `interfaces/web/world.py`, `interfaces/web/world_schemas.py`, `models/location.py`, `models/game_state.py`, `formatting/entity_markup.py`

## Context

ADR-0006 gave the player web UI its structure (Story / Character / Map panes, `WorldView` on every payload), and ADR-0010 made in-prose entities and map places tappable through a language-neutral gesture contract. Neither record decided what the UI should *look like*, and the styling grew incidentally: Georgia on `#1a1a1a`, a gold accent reused for almost everything, and unrelated one-off hues (dusty-pink submit buttons, mauve player lines with a terminal-style `> ` prefix).

That left four concrete problems:

- **Colour said nothing reliable.** NPC spans were light blue, but so was every italic (atmosphere, thoughts, quoted speech), so decorative emphasis read as a tappable person. Gold marked places, bold text, the character name, the current location, the clock and the active tab alike, so it carried no meaning. Items were a third, unrelated neon green.
- **Where / when / who was hidden.** On a phone the location, clock and people present lived behind the Map and Character tabs. A reader scrolling prose lost the scene's context.
- **English enum slugs leaked into the chrome.** The clock printed the raw `time_of_day` slug (`"Day 2 · evening"`) and location types surfaced as English words. Russian is the primary play language (ADR-0010), so this is the same class of leak ADR-0010 closed on the action side, now appearing on the display side.
- **No identity.** Storyteller's architecture is literally a theatre: a Director runs a cast of performers and the Narrator speaks the prose. The UI gave no hint of that, and nothing a beta tester would remember.

Constraints carried from earlier decisions: stay vanilla with no build step, keep the layout mobile-first, keep `PRECACHE_URLS` unchanged (ADR-0006, ADR-0010, D006), take new data only from `WorldView`, and route NPC naming only through `NPCCard.label_for_player`.

## Decision

Adopt one visual language for `interfaces/web/static/`, called **"the stage"**. The house is dark, the stage is lit (place, time and cast), the prose is set like a book, and the player's own lines are set as stage cues.

1. **Design tokens on `:root` in `style.css`.** Surfaces (`--bg`, `--bg-elev`, `--bg-raised`), ink (`--ink` … `--ink-faint`), accents (`--brass`, `--velvet`), semantic hues (below), font stacks, measure and spacing are all tokens. The theme is dark only (`color-scheme: dark`). `--bg` is `#13100d`, and the same value is written to `<meta name="theme-color">` and to the manifest's `theme_color` / `background_color`.
2. **Colour carries meaning and nothing else.**
   - `--person` (warm rose) marks people: NPC spans, known cast chips, known-people names.
   - `--place` (gold) marks places: POI spans (the default `.poi` hue) and map places.
   - `--thing` (sage) marks objects the player can handle: `item` spans and inventory-list markers.
   - Each semantic hue has a `-dim` variant (underline) and a `-wash` variant (hover / open background).
   - `--brass` is the stage light and interface emphasis. `--velvet` is the curtain and is used only for brand accents.
   - Italics stay ink-toned, so atmospheric emphasis never reads as a tappable name.
   - The hue is keyed on the same `data-kind` values that `formatting.entity_markup.wrap_entities` emits and that ADR-0010 gestures accept (`npc` / `poi` / `item`).
3. **Self-hosted SIL OFL fonts.** Two families ship in `interfaces/web/static/fonts/`, served by the existing `/static` `StaticFiles` mount:
   - **Literata** for prose: a variable `wght` axis, normal and italic.
   - **Cormorant Garamond 600** for display titles.
   - Each face ships **Latin and Cyrillic** `unicode-range` subsets.
   - The OFL licence text sits next to the files (`OFL-Literata.txt`, `OFL-Cormorant.txt`).
   - Loading uses `font-display: swap` with serif fallbacks (`"PT Serif", Georgia, …`). The Latin and Cyrillic normal Literata files are `preload`ed (the chrome is Latin; Russian is the primary story language).
   - No third-party font origin is used.
4. **A sticky stage header in the Story pane** (`#stage`, `position: sticky; top: 0`) shows:
   - the ancestor breadcrumb and current place name, as a button that opens the Map pane;
   - the clock, as a daypart icon plus `Day N · HH:00`;
   - up to four cast chips plus a `+N` chip, with known people as solid rose chips and strangers as dashed italic chips.

   All of it is rendered from the existing `WorldView` (`map.breadcrumb`, `map.current`, `clock`, `people`). There is no new endpoint and no new field. Chip text is `ScenePerson.label` only, and the tooltip is the scene `role`. The clock also sets `body[data-daypart]`, which tints the stage-light gradient.
5. **Player lines are stage cues.** `.turn.player` renders as a brass rule followed by a quieter italic line in `--ink-soft`. This applies to both the optimistic free-text echo and a gesture's server-composed `action_html` (ADR-0010). The change is presentational only. Cue text for gestures still comes only from the server.
6. **Location types and times of day are drawn, not written.** Two inline-SVG tables in `app.js` replace the printed slugs:
   - `PLACE_ICONS` is keyed by `models/location.py` `LOCATION_TYPES`: `building`, `district`, `city`, `region`, `country`, `generic`.
   - `DAYPART_ICONS` is keyed by the `models/game_state.py` dayparts: `morning`, `afternoon`, `evening`, `night`.

   The slug survives only as a `title` tooltip. The icons are strings inside the precached `app.js`, not separate files.
7. **ADR-0006's shell constraints still hold.**
   - The UI stays vanilla HTML, CSS and JS with no build step.
   - The phone layout remains the baseline (bottom tab bar, safe-area insets), and desktop gets the side rail as an enhancement.
   - `prefers-reduced-motion` turns off animations and transitions.
   - `PRECACHE_URLS` is unchanged, and fonts are **not** added to it. Only `CACHE_NAME` is bumped (`v2` to `v3`) to evict the old shell, following the ADR-0010 precedent.

This ADR is **Proposed**, not self-accepted: it sets the player-facing product surface, which is Max's call (ADR-0004, ADR-0006, ADR-0010).

## Rationale

- **The metaphor is the architecture.** Director, cast and Narrator are real module boundaries (`cast/`), and the UI makes them visible to the player. The lit stage holds what the Director established (place, time, who is on stage). The book page holds what the Narrator said. The cue holds what the player said. This gives the beta a recognisable identity without inventing a theme unrelated to the product.
- **Semantic colour completes ADR-0010's tap-to-act.** A tappable word should say what kind of thing it is before it is tapped. Mapping hue 1:1 to the gesture contract's `entity_kind` means the colour predicts the offered action (`talk` for people, `examine` for things and places). Keeping italics in ink prevents the decorative emphasis LLM prose uses heavily from being mistaken for an entity.
- **The stage header answers where, when and who without leaving the prose.** On a phone, reading and orientation used to compete for the same pane. Driving the header from `WorldView` keeps it per-turn-fresh and atomically consistent with the narration it sits above (ADR-0006 §4). Reading chip text only from `ScenePerson.label` keeps the ADR-0006 §5 single name-gating path intact.
- **Self-hosting avoids adding a third-party origin to every page view.** Google Fonts or a font CDN would send every tester's IP to a new third party, and the D007 privacy notice covers AI model providers, not font hosts. Same-origin files also avoid a runtime dependency on another host's availability. Supabase auth (a pre-existing `cdn.jsdelivr.net` script) stays the only external asset. SIL OFL allows redistribution when the licence ships with the fonts.
- **The Cyrillic subsets are not optional.** Russian is the primary play language (ADR-0010). A Latin-only face would render Russian prose in the fallback serif, so the book setting would change font mid-page between languages. `unicode-range` means an English session never downloads the Cyrillic files.
- **Literata and Cormorant, specifically.** Literata was designed for long-form reading on screens and ships as a variable font: one file per style covers every weight used. Cormorant Garamond gives a theatrical display face with Cyrillic coverage at a single weight (600), which keeps it small.
- **Icons close the display-side English leak without an i18n layer.** Location-type and daypart slugs are fixed backend vocabularies, so a closed set of drawn icons makes them readable in any story language at zero translation cost. Inline SVG strings ride the precached `app.js`, so no new asset or cache entry is needed.
- **Not precaching fonts keeps D006 honest and cheap.** Gameplay is online-required, and offline the app shows only a notice. Precaching about 195 KiB of fonts would slow service-worker install and would break the ADR-0006 / ADR-0010 guardrail, with nothing gained for the player.

## Alternatives considered

### Alternative 1: Keep the previous generic dark UI

This had zero risk and no new assets. It was rejected because it left tap targets undifferentiated after ADR-0010, kept where / when / who behind tabs on phones, and kept printing English enum slugs in Russian sessions.

### Alternative 2: Load fonts from Google Fonts or a CDN

This is the least effort: one `<link>`, with subsetting done by the provider. It was rejected because it adds a third-party origin to every page view, outside the D007 disclosure, and a runtime dependency on another host. Self-hosting costs about 195 KiB in the repo.

### Alternative 3: System font stack only

This ships zero bytes and loads fastest. It was rejected because system serifs differ widely across Android, iOS and desktop, especially for Cyrillic, so the "book" would look different on every tester's device. The system stack is kept as the `font-display: swap` fallback.

### Alternative 4: Add the fonts to `PRECACHE_URLS`

This would give the offline shell the brand typography. It was rejected because it breaks the ADR-0006 / ADR-0010 guardrail, makes service-worker install download about 195 KiB, and buys nothing for gameplay, which is online-required (D006).

### Alternative 5: Localise the chrome (a UI i18n layer) instead of drawing icons

This is the complete fix for English chrome. It was **deferred** as a larger, separate decision (string catalogue, locale plumbing to the client, EN/RU parity tests). Icons fix the two enum-slug leaks now, and the remaining English chrome is recorded under Tradeoffs.

### Alternative 6: A separate icon sprite or icon font

This is tidier than SVG strings in JS. It was rejected because a new file must either change `PRECACHE_URLS` or be uncached shell chrome. A handful of inline SVG strings in the precached `app.js` avoid both problems.

### Alternative 7: Light, sepia or user-selectable themes

A reading app often offers these. They were **deferred**. The dark house is the metaphor, a single theme halves the token surface to maintain, and no beta feedback has asked for another theme yet. The token layer makes adding one later a `:root` override, not a rewrite.

## Consequences

Positive consequences:
- Where, when and who stay visible above the prose on every screen size, consistent with the turn's narration.
- In-prose tap targets show their kind by hue, and that hue predicts the ADR-0010 gesture on offer.
- Location-type and daypart chrome reads the same in every story language.
- No toolchain, endpoint, payload field or engine change was added, and `PRECACHE_URLS` is unchanged.
- The palette and type live in one token block, so future UI work has one vocabulary to follow.

Tradeoffs / risks:
- **About 195 KiB of fonts.** The sizes are: Literata Latin 52 + 54 KB, Literata Cyrillic 28 + 29 KB, Cormorant Latin 23 KB, Cormorant Cyrillic 13 KB. Both normal Literata subsets are preloaded, so an English session also fetches the 28 KB Cyrillic file; italics and display faces still swap in (brief FOUT on first load).
- **Fonts are not in the service-worker cache.** `networkFirst` fetches them but `shouldCacheShell` stores only `PRECACHE_URLS` paths. When offline and without a warm HTTP cache, the shell falls back to system serifs. This is accepted under D006.
- **Hue is the only in-prose kind cue.** Once tapped, the popover's title marker is shape-coded as well as coloured (person ●, place ◆, thing ■), and its action list differs by kind. Before tapping, players with colour-vision deficiency cannot tell a person from a thing. **Open question:** add a non-colour cue in the prose itself if beta feedback shows confusion.
- **Dark only.** There is no light or high-contrast mode.
- **English chrome remains.** This includes `Day N · HH:00`, the tab labels (Story / Character / Map), the fact-source titles, and `<html lang="en">`. The icons remove only the enum-slug leaks, not all English chrome.
- **The stage light is progressive.** It animates via `@property --stage-light`, and browsers without `@property` snap between tints instead of fading.
- **`style.css` roughly doubled** (937 to 1716 lines). It is still one precached file, but it is a larger surface to keep token-disciplined.
- **The `CACHE_NAME` bump** means installed PWAs replace the v2 shell on their next online load.

What future agents must preserve:
- **Colour is semantic.**
  - `--person` / `--place` / `--thing` map 1:1 to entity kinds (`npc` / `poi` and map places / `item`).
  - Do not reuse these hues for decoration, and do not colour italics or emphasis in an entity hue.
  - A new entity kind in `wrap_entities` or the gesture contract gets its own `base` / `-dim` / `-wash` token triple.
- **Tokens first.** Add colours as `:root` tokens rather than new hex literals. Keep `--bg`, `<meta name="theme-color">` and the manifest `theme_color` / `background_color` in sync (`tests/test_web_api.py` asserts `#13100d` in both places).
- **The stage header reads only `WorldView`.** Do not add a separate endpoint or client-side derivation for place, time or cast. Cast chip text comes only from `ScenePerson.label` (the `NPCCard.label_for_player` path), and no other NPC name field may be rendered there.
- **Cue text is never composed client-side.** The stage-cue styling is presentational. Gesture cue text comes only from the server's `action_html` (ADR-0010).
- **Fonts stay self-hosted under `static/fonts/` with their OFL licence files.** Do not add Google Fonts or CDN font links. When adding a weight or style, ship the Latin and Cyrillic subsets together (EN/RU parity).
- **Chrome is drawn, not written.** Keep `PLACE_ICONS` keys equal to `LOCATION_TYPES` and `DAYPART_ICONS` keys equal to the `game_time` values. A new backend slug needs an icon. Location types fall back to `generic`, but an unknown daypart renders no icon.
- **Shell constraints.** Do not add fonts or icon files to `PRECACHE_URLS`, and bump `CACHE_NAME` when the shell must evict old caches. Keep the UI vanilla and mobile-first, and keep honouring `prefers-reduced-motion` and safe-area insets.
- **Light themes and chrome i18n need a new decision.** Treat them as new decisions that extend this one, not as incidental tweaks.

## Verification / tests

- **Theme colour parity (automated).** `tests/test_web_api.py::test_get_index_exposes_pwa_metadata_and_offline_notice` and `::test_get_manifest_serves_installable_metadata` assert `#13100d` for the meta tag and the manifest.
- **Online-required shell (automated).** `tests/test_web_api.py` (the `GET /sw.js` test) asserts the service worker still only caches `PRECACHE_URLS` paths. `git diff main -- interfaces/web/static/sw.js` should show only the `CACHE_NAME` line.
- **Name-gating (automated, pre-existing).** `tests/test_web_world.py` covers `ScenePerson.label` coming from `NPCCard.label_for_player`. Inspection confirms `renderStage` in `app.js` reads only `person.label`, `person.role` and `person.known`.
- **Icon-key parity (automated).** `tests/test_web_static_icons.py` reads the `PLACE_ICONS` / `DAYPART_ICONS` tables out of the shipped `app.js` and asserts their keys equal `models/location.py` `LOCATION_TYPES` and the labels `GameState.advance_clock` produces over a full day.
- **Font serving and licensing (inspection).** `GET /static/fonts/*.woff2` is served by the `StaticFiles` mount in `interfaces/web/app.py`, and each family's `OFL-*.txt` is present next to its files.
- **Demo Contract for `interfaces/web/`.** Boot the app and include phone- and desktop-width screenshots in the PR showing the stage header, cues, entity hues and map icons. Include a Russian session so the Cyrillic subsets are exercised.
- **Standard gauntlet.** ruff, format, flake8, mypy, pytest.
- **Reference screenshots.** `docs/design/stage-ui/` holds before/after captures (desktop 1440×900, phone 390×844, Russian session, mocked API) of the play screen, map, library, new-story form and opening curtain. Compare new UI work against them.

## Related files

- `interfaces/web/static/style.css` (tokens, `@font-face`, stage, cues, entity hues)
- `interfaces/web/static/app.js` (`PLACE_ICONS`, `DAYPART_ICONS`, `renderStage`, `fillClock`)
- `interfaces/web/static/index.html` (`#stage`, font preload, `theme-color`)
- `interfaces/web/static/sw.js` (`CACHE_NAME`, unchanged `PRECACHE_URLS`)
- `interfaces/web/static/manifest.webmanifest`
- `interfaces/web/static/fonts/` (`*.woff2`, `OFL-Literata.txt`, `OFL-Cormorant.txt`)
- `interfaces/web/world.py`, `interfaces/web/world_schemas.py`
- `formatting/entity_markup.py`
- `models/location.py`, `models/game_state.py`, `models/npc_card.py`
- `tests/test_web_api.py`, `tests/test_web_world.py`, `tests/test_web_static_icons.py`
- `docs/decisions/0006-player-dashboard-gui.md`
- `docs/decisions/0010-language-neutral-player-action-contract.md`
- `docs/studio/09-founder-decision-register.md` (D006, D007)
