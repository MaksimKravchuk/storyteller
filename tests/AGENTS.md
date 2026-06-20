---
type: Component
title: Tests
description: Deterministic unit, integration, DB, E2E, and benchmark test guidance.
resource: tests/
tags: [tests, quality, allure]
---

# Directory Instructions

Root `AGENTS.md`, `CLAUDE.md`, and `tests/README.md` remain authoritative. This
file adds local context for `tests/`.

# Boundary

`tests/` owns automated verification. Non-e2e tests must use Allure epic,
feature, story, and title labels.

# Local Rules

- For bug fixes, write and observe the failing regression test before the fix.
- Prefer consumer-side integration seams for wiring regressions.
- Do not add lint, type, or test suppressions without explicit approval.
- Paid E2E and benchmark checks require approval.

