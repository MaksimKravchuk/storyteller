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
It translates HTTP to engine/repository calls and builds player-facing DTOs.
Moderation, turn logic and persistence rules stay in `safety/`,
[engine](/engine/AGENTS.md) and [db](/db/AGENTS.md).

# Contents

- `app.py` — `create_app()`: routers, player-id middleware, `/static` mount,
  generic 500 handler.
- `routes*.py` — thin handlers: game/actions (`routes.py`), SSE turn stream
  (`routes_stream.py`), library, posters, feedback; auth in `auth_routes.py`.
- `service*.py` — business logic behind routes; `service_helpers.py` owns
  engine restore and snapshots; `runtime.py` runs start/turn with persistence.
- `deps.py` — cached `get_cfg`, session factory, `get_repo`, player cookie.
- `auth.py`, `auth_models.py`, `beta_auth.py`, `beta_policy.py`,
  `quota_locks.py` — Supabase auth, beta access, quotas and spend budget.
- `errors.py`, `action_errors.py`, `poster_errors.py` — service errors and
  their HTTP mapping.
- `action_stream.py` — SSE response for one turn (ADR-0022).
- `schemas*.py`, `character*.py`, `world*.py` — Pydantic DTOs and builders
  (`WorldView`, ADR-0006).
- `player_gestures.py` — server-side gesture → localized action phrase
  (ADR-0010).
- `transcript.py`, `playbill.py`, `library_rows.py`, `poster_art.py`,
  `pwa.py`, `readiness.py` — rendering, library posters (ADR-0020), PWA
  files, `/readyz`.

# Local Rules

- Keep route/service behavior above [engine](/engine/AGENTS.md).
- Verify player-facing layout in a browser for UI changes.
- Keep static asset changes scoped under [static assets](/interfaces/web/static/AGENTS.md).
- Test routes with `TestClient` and `app.dependency_overrides` on
  `deps.get_repo` / `get_cfg` (see `tests/test_web_api.py`); no real DB.

# Patterns

- Handlers catch the `action_errors.ACTION_ERRORS` tuple in one `except` and
  call `to_http_exception` (`routes.py`, `routes_poster.py`,
  `action_stream.py`); add new service errors there, not per route.
- New per-turn data rides `GameSnapshot` / `ActionResponse` (`WorldView`),
  not a new endpoint (ADR-0006).
- NPC names shown to the player come only from
  `NPCCard.label_for_player` (ADR-0006, ADR-0010).
- Restore engines through `service_helpers.restore_engine`, which calls
  `engine.session_restore.restore_engine_with_admin_settings`.
- Spend-producing work runs under `quota_locks.player_lock(player_id)`.

# Anti-patterns

- Do not let the client send natural-language for taps; it sends a gesture
  and `player_gestures.py` composes the phrase server-side (ADR-0010).
- Do not call `create_engine_from_state` directly to resume; admin
  model/search overrides were skipped that way (commit eb30c09).
- Do not drop buffered AI-call logs on a failed turn; `runtime.py`
  `_commit_failed_spend` keeps them so the budget gate sees the spend
  (commit 711d765).
- Do not return exception text to the player; `app.py` and
  `action_stream.py` send generic details (ADR-0022).
- Do not change the non-streamed `POST .../actions` contract; `done` must
  carry the same `ActionResponse` (ADR-0022).

# Related

- [Interfaces](/interfaces/AGENTS.md)
- [DB](/db/AGENTS.md)
- [Engine](/engine/AGENTS.md)
