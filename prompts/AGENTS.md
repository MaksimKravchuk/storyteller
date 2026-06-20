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
locale-specific prompt text.

# Local Rules

- Prompt-variable changes require consumer-side tests.
- Keep EN/RU locale pairs aligned when editing localized prompt behavior.
- Coordinate response shape assumptions with [cast schemas](/cast/schemas/AGENTS.md).
- Narrative-affecting prompt changes may require approved benchmark evidence.

# Related

- [Cast](/cast/AGENTS.md)
- [LLM](/llm/AGENTS.md)

