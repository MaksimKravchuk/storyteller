---
type: Component
title: Safety
description: Moderation providers, heuristic fallback, thresholds, and safety result models.
resource: safety/
tags: [safety, moderation, policy]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `safety/`.

# Boundary

`safety/` owns moderation providers, heuristic fallback behavior, thresholds,
and safety result models.

# Local Rules

- Keep provider-specific moderation behind factory and provider seams.
- Do not weaken policy thresholds without an explicit decision.
- Test provider-independent behavior without live paid calls.

# Related

- [Engine](/engine/AGENTS.md)
- [LLM](/llm/AGENTS.md)

