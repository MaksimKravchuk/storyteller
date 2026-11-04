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
is FastAPI under `web/`; the admin dashboard here is a FastAPI router mounted
at `/admin` inside the same app (one process, one port, one auth stack).
Telegram and CLI clients were retired (ADR-0004); do not add new clients.

# Contents

- `admin.py` — the `/admin` router: the `_ROUTES` table and `_build_router()`,
  which gates `/admin/api/*` with `Depends(require_admin)`.
- `admin_auth.py` — `require_admin` dependency (401/403).
- `admin_route_helpers.py` — `get_cfg`, `open_repo`, `session_scope` shared
  by handlers.
- `admin_json.py` — `_json_response` with date/UUID serialisation.
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
- Admin `/admin/api/*` routes are gated by the account admin role (ADR-0021)
  through the `require_admin` dependency on the `api` sub-router; any route
  that needs auth must be registered there.

# Patterns

- Admin handlers open the DB through
  `admin_route_helpers.open_repo(request)` / `session_scope(request)` and
  reply with `admin_json._json_response` (copy `admin_routes_detail.py`).
- Register a new route as one row in the `_ROUTES` table in `admin.py`.
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
