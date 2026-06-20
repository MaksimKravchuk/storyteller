---
type: Component
title: Models
description: Domain models for game state, settings, characters, NPC cards, scenes, locations, goals, and visible entities.
resource: models/
tags: [models, domain, pydantic]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `models/`.

# Boundary

`models/` owns Pydantic domain objects. Domain models stay separate from ORM
rows in [db](/db/AGENTS.md).

# Local Rules

- Adding a model field that a downstream consumer must read requires a
  consumer-side integration test.
- Coordinate persisted fields with [db converters](/db/converters/AGENTS.md).
- This directory is in the mutation-testing scope.

# Related

- [Cast schemas](/cast/schemas/AGENTS.md)
- [Knowledge](/knowledge/AGENTS.md)

