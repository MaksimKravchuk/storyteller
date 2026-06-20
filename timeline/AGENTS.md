---
type: Component
title: Timeline
description: Game clock, scheduled events, time costs, and event effects.
resource: timeline/
tags: [timeline, events, game-clock]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `timeline/`.

# Boundary

`timeline/` owns game-clock advancement, scheduled events, time costs, and event
effects.

# Local Rules

- Preserve deterministic behavior for event and time-cost logic.
- Prove changes with unit tests around the consumer that applies the event.
- This directory is in the mutation-testing scope.

# Related

- [Engine](/engine/AGENTS.md)
- [Models](/models/AGENTS.md)

