---
type: Component
title: Cast Schemas
description: Structured response models shared by Director planning and performer agent outputs.
resource: cast/schemas/
tags: [cast, schemas, pydantic]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `cast/schemas/`.

# Boundary

`cast/schemas/` defines typed payloads for action plans, performer outputs, and
turn outputs.

# Local Rules

- Treat schema fields as contracts with the consumer that reads them.
- For new fields, add tests at the consumer seam, not only model validation.
- Keep schema names and access helpers aligned with [cast](/cast/AGENTS.md)
  runtime usage.

# Related

- [Models](/models/AGENTS.md)
- [Prompts](/prompts/AGENTS.md)

