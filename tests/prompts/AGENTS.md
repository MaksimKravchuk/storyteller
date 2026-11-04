---
type: Component
title: Prompt Seam Tests
description: Consumer-seam contract tests proving prompt sections actually reach the LLM call.
resource: tests/prompts/
tags: [tests, prompts, consumer-seam, locale]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `tests/prompts/`.

# Boundary

`tests/prompts/` owns tests that capture the prompt a performer sends to a
mocked LLM and assert expected sections and values are in it (ADR-0002).
Template-only rendering or locale-parity checks stay in `tests/`
(e.g. `tests/test_prompt_localization.py`).

# Contents

- `test_consumer_seam_contract.py` — `TestConsumerSeamContract` re-renders
  every `PromptSection` per performer x locale and asserts each appears in
  the captured prompt; `TestContrivedBugIsCaught` proves the assert fires.
- `_consumer_seam_state.py` — `build_maximal_game_state()` so every
  section's `required_vars` are satisfiable from real data.
- `_consumer_seam_kwargs.py` — per-performer section-kwargs builders that
  mirror each consumer's `set_context` calls, plus LLM mock helpers.
- `_consumer_seam_cases.py` — `PerformerCase` list (`CASES`) over English
  and Russian.
- `test_actor_derived_mood_seam.py`, `test_actor_memory_relevance.py` —
  focused seams for single values reaching the Actor prompt.

# Local Rules

- A new model field a prompt should read needs a test here that reads the
  captured `system_prompt` / user message, not the supplier's output.
- Cover both locales (`"English"` and `"Russian"`) for every case.
- New performer: follow the "Adding a new performer" steps in the
  `test_consumer_seam_contract.py` docstring (kwargs builder, case, state).
- Split helpers across the three `_consumer_seam_*` modules to stay inside
  the WPS import-count budget rather than suppressing it.

# Patterns

- Capture at the LLM seam:
  `llm_client.send_message.call_args.kwargs["system_prompt"]`, the same
  place `cast/base_performer_class.py` writes to.
- Build state with `state_mod.build_maximal_game_state()` and reuse
  `kwargs_mod` helpers, as `test_actor_derived_mood_seam.py` does.
- Prove a new guard is load-bearing by breaking it on purpose with
  `monkeypatch`, like `TestContrivedBugIsCaught`.

# Anti-patterns

- Asserting only that a supplier returns a value: the
  `NPCCard.known_names_for_player` alias list passed supplier tests yet
  never reached the Narrator prompt (ADR-0002, CLAUDE.md Testing).
- Assuming a missing var raises: `PromptTemplate.render` silently skips a
  section whose `required_vars` are absent (`prompts/base_template.py`).
- Testing only the English template: RU drift is a known regression class
  (CLAUDE.md locale-parity escalation rule).

# Related

- [Tests](/tests/AGENTS.md)
- [Prompts](/prompts/AGENTS.md)
- [Cast](/cast/AGENTS.md)
