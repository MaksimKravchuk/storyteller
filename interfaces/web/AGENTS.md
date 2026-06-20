---
type: Component
title: Web Interface
description: FastAPI player web UI and web-facing schemas, routes, services, and static assets.
resource: interfaces/web/
tags: [interfaces, fastapi, web]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `interfaces/web/`.

# Boundary

`interfaces/web/` exposes Storyteller through FastAPI routes and browser assets.

# Local Rules

- Keep route/service behavior above [engine](/engine/AGENTS.md).
- Verify player-facing layout in a browser for UI changes.
- Keep static asset changes scoped under [static assets](/interfaces/web/static/AGENTS.md).

# Related

- [Interfaces](/interfaces/AGENTS.md)
- [DB](/db/AGENTS.md)

