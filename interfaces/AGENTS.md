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
[engine](/engine/AGENTS.md) and [db](/db/AGENTS.md) boundaries. The player UI
is FastAPI under `web/`; the admin dashboard here is a separate aiohttp app.
Telegram and CLI clients were retired (ADR-0004); do not add new clients.

# Contents

- `admin.py` — aiohttp admin app: route registration and `_auth_middleware`.
- `admin_auth.py` — `admin_denial()` (401/403) and `GET /config/public`.
- `admin_route_helpers.py` — app keys, `get_cfg`, `open_repo`,
  `session_scope`, JSON serialisation shared by handlers.
- `admin_routes*.py` — handlers grouped by area: sessions/users,
  detail, entity, feedback, beta invites, reliability, settings, search
  settings (plus `_helpers` / `_validation` modules).
- `admin_reports.py` — beta cost summary report.
- `admin_dashboard.html` — single-file vanilla HTML/JS dashboard.
- `web/` — the player web UI (see its own AGENTS.md).

# Local Rules

- Do not reach into performer internals from route code.
- Web or admin UI changes need a local app demo and screenshot or notes in the
  PR.
- Admin `/api/*` routes are gated by the account admin role when beta auth is
  on (ADR-0021). The middleware only checks the `/api/` prefix, so any
  route that needs auth must live there.

# Patterns

- Admin handlers open the DB through
  `admin_route_helpers.open_repo(request)` / `session_scope(request)` and
  reply with its JSON helper (copy `admin_routes_detail.py`).
- Register routes in the matching `_setup_*_routes` function or method in
  `admin.py`.
- Keep handler modules small: split validation and helpers into sibling
  modules (`admin_routes_settings_validation.py`,
  `admin_routes_settings_search_helpers.py`) to stay inside WPS limits.
- Allowed admin values come from their owner, e.g.
  `db.repo_settings_search.ALLOWED_SEARCH_PROVIDERS`.

# Anti-patterns

- Do not reintroduce a shared admin token (`ADMIN_TOKEN` was removed by
  ADR-0021); auth is Supabase JWT plus `accounts.is_admin`.
  `tests/test_admin_auth.py` covers the 401/403 cases.
- Do not put player- or LLM-derived text into `admin_dashboard.html` via
  `innerHTML` without `escapeHtml()` (commit 711d765 fixed this).
- Do not compute admin settings overrides in interface code; resume goes
  through `engine.session_restore` (commit eb30c09 fixed overrides being
  skipped on resume).

# Related

- [Web interface](/interfaces/web/AGENTS.md)
- [DB](/db/AGENTS.md)
- [Engine](/engine/AGENTS.md)
