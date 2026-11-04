---
type: Component
title: Formatting
description: Deterministic Markdown rendering and entity markup helpers for player-visible text.
resource: formatting/
tags: [formatting, markdown, entity-markup]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `formatting/`.

# Boundary

`formatting/` owns deterministic rendering and entity markup helpers for
player-visible text. Deciding which entities are visible belongs to
[cast](/cast/AGENTS.md) (`cast/visible_entities.py`); wiring into responses
belongs to `interfaces/web/transcript.py`.

# Contents

- `markdown_render.py` — `to_html`: escaped bold/italic/code subset with
  `<p>` paragraphs; everything else is literal text.
- `entity_markup.py` — `wrap_entities(html, entities, language)` wraps alias
  hits in `<span class="poi" data-kind data-id>`.
- `entity_lemmatizers.py` — `pick_lemmatizer`, `pick_noun_test` (pymorphy3
  for Russian, exact lowercase otherwise).
- `entity_short_forms.py`, `entity_ambiguity.py` — short NPC forms and the
  filter that drops forms shared by another entity.

# Local Rules

- Keep rendering deterministic and dependency-light.
- Test escaping, entity wrapping, and language-specific behavior directly.

# Patterns

- Render first, then wrap: `interfaces/web/transcript.py` calls `to_html`
  and passes the result to `wrap_entities`, which only rewrites text nodes.
- Plans are sorted longest-first so a full alias beats its short form.
- Pass a shared `token_cache` when wrapping many lines (transcript reload).
- Missing pymorphy3 degrades to exact match with a loud log, never an error.

# Anti-patterns

- Feeding unescaped text to `wrap_entities`; it relies on `to_html` having
  escaped player-controlled content (its docstring).
- Linking a role or short form two NPCs share, or an adjective-only head;
  mentions linked the wrong person (#376; `tests/test_entity_markup.py`).
- Wrapping an un-introduced NPC's real name; aliases must come from
  `known_names_for_player` (`tests/test_watchman_regression.py`).
- Adding `data-kind` values the client and gestures do not accept
  (`docs/decisions/0019-player-ui-stage-visual-language.md`).

# Related

- [Models](/models/AGENTS.md)
- [Web interface](/interfaces/web/AGENTS.md)
- [Cast](/cast/AGENTS.md)
