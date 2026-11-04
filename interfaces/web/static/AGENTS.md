---
type: Component
title: Web Static Assets
description: Browser-side CSS, JavaScript, icons, and static files used by the player web UI.
resource: interfaces/web/static/
tags: [interfaces, frontend, static-assets]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `interfaces/web/static/`.

# Boundary

`interfaces/web/static/` holds browser assets for the player web UI. It
renders what the API returns; it does not derive game state, compose action
text, or resolve NPC names. Vanilla HTML/JS/CSS only: no framework, bundler
or build step (ADR-0006).

# Contents

- `index.html` — the single page shell; loads `style.css`, supabase-js and
  `app.js`.
- `app.js` — the whole client in one IIFE: auth, library, character
  creation, SSE turn stream, stage header, map, entity popovers.
- `style.css` — "the stage" visual language; design tokens on `:root`
  (ADR-0019).
- `sw.js` — PWA service worker: network-first shell cache, API never cached.
- `manifest.webmanifest`, `icons/` — PWA metadata and app icons.
- `fonts/` — self-hosted Literata and Cormorant WOFF2 subsets with OFL
  licence files.

# Local Rules

- Keep UI changes consistent with [web interface](/interfaces/web/AGENTS.md)
  behavior.
- Verify responsive rendering for layout changes (mobile-first; desktop is the
  enhancement).
- Keep honouring `prefers-reduced-motion` and safe-area insets (ADR-0019).

# Patterns

- Call the API through `apiFetch()` in `app.js`, which adds the auth header.
- Add colours as `:root` tokens in `style.css`; entity hues map 1:1 to
  `data-kind` (`--person` npc, `--place` poi, `--thing` item), each with
  `-dim` / `-wash` variants.
- Escape plain text with `escapeHTML()`; only server-rendered HTML (turn
  prose with entity spans) goes straight into `innerHTML`.
- Taps send `{gesture: {intent, entity_kind, entity_id}}` and render the
  server's `action_html` (ADR-0010).
- A new location type or daypart needs a key in `PLACE_ICONS` /
  `DAYPART_ICONS`; `tests/test_web_static_icons.py` checks them against the
  backend vocabularies.

# Anti-patterns

- Do not compose action or cue text client-side (ADR-0010, ADR-0019).
- Do not add Google Fonts or CDN font links; ship Latin and Cyrillic
  subsets together (ADR-0019).
- Do not let `sw.js` handle cross-origin requests; it masked Supabase errors
  as offline 503s (commit 061f211).
- Do not cache `/api/` or non-GET requests, or add fonts/icons to
  `PRECACHE_URLS`; bump `CACHE_NAME` when old shells must be evicted.
  `tests/test_web_api.py` checks the service worker.
- Keep `--bg`, `<meta name="theme-color">` and the manifest colours equal
  (`#13100d`); `tests/test_web_api.py` asserts it.

# Related

- [Web interface](/interfaces/web/AGENTS.md)
- [Interfaces](/interfaces/AGENTS.md)
