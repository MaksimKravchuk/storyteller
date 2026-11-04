---
type: Component
title: Prompts
description: Composable prompt templates and localized prompt sections consumed by cast agents.
resource: prompts/
tags: [prompts, localization, agents]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `prompts/`.

# Boundary

`prompts/` owns prompt templates, prompt sections, required variables, and
locale-specific prompt text. It must not build context values, read game
state, or call LLMs; the consuming performer in [cast](/cast/AGENTS.md) does.

# Contents

- `base_template.py` — `PromptSection` (`name`, `template`, `required_vars`)
  and `PromptTemplate`, which silently skips sections with missing vars.
- `locales.py` — `Locale` enum, `resolve_locale` (aliases, English
  fallback) and `make_locale_lookup`.
- One EN/RU module pair per agent: `actor_prompts`, `anachronism_classifier`,
  `chronicler_prompts`, `data_miner_prompts`, `director_prompts`,
  `dramaturge_prompts`, `item_generator_prompts`, `narrator_prompts`,
  `npc_generator_prompts`, `scene_builder_prompts` (`*.py` + `*_ru.py`).

# Local Rules

- Prompt-variable changes require consumer-side tests.
- Keep EN/RU locale pairs aligned when editing localized prompt behavior.
- Coordinate response shape assumptions with [cast schemas](/cast/schemas/AGENTS.md).
- Narrative-affecting prompt changes may require approved benchmark evidence.
- Touching a `PromptSection` or `required_vars` is a feature-factory
  escalation trigger (root `CLAUDE.md`).

# Patterns

- The EN module defines the templates, imports the `_RU` ones, and exposes a
  frozen bundle dataclass via `make_locale_lookup` (`get_narrator_prompts` in
  `narrator_prompts.py`). New locales plug in there.
- The Russian twin keeps identical section names, order and
  `required_vars`; only the text changes (`narrator_prompts_ru.py`).
- Optional context is its own section whose `required_vars` gate it, e.g.
  `wait_context` and `turn_intent` in `NARRATOR_NARRATE`.
- JSON examples inside templates escape braces as `{{ }}` because rendering
  is `str.format` (`SCENE_BUILDER_GENERATE`).
- RU text keeps enum literals and JSON keys in English so schemas still
  parse (`tests/test_prompt_localization.py`, NPCGenerator catalog test).

# Anti-patterns

- Adding or renaming a var in one locale only; the other locale silently
  drops the section. Guarded by `_assert_section_parity` in
  `tests/test_prompt_localization.py`.
- Adding a section var without wiring it in the performer's `set_context`;
  supplier tests pass but the prompt never shows it (the
  `known_names_for_player` regression). Guarded by
  `tests/prompts/test_consumer_seam_contract.py`
  (`docs/decisions/0002-prompt-consumer-seam-contract-tests.md`).
- Adding a `render_strict` or raising on missing vars; ADR-0002 keeps
  silent-skip semantics on purpose.
- Hardcoding English action verbs for player input; Russian is the primary
  play language (`docs/decisions/0010-language-neutral-player-action-contract.md`).

# Related

- [Cast](/cast/AGENTS.md)
- [LLM](/llm/AGENTS.md)
- [Prompt tests](/tests/prompts/AGENTS.md)
