---
type: Component
title: Interfaces
description: HTTP-facing player and admin surfaces for running and inspecting Storyteller.
resource: interfaces/
tags: [interfaces, web, admin]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `interfaces/`.

# Boundary

`interfaces/` owns HTTP-facing player and admin surfaces. It should stay above
[engine](/engine/AGENTS.md) and [db](/db/AGENTS.md) boundaries.

# Local Rules

- Do not reach into performer internals from route code.
- Web or admin UI changes need a local app demo and screenshot or notes in the
  PR.

# Related

- [Web interface](/interfaces/web/AGENTS.md)

