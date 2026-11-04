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
and safety result models. Where moderation runs (the `process_action` seam,
`SentenceGate`) belongs to [engine](/engine/AGENTS.md); HTTP mapping belongs
to [interfaces](/interfaces/AGENTS.md).

# Contents

- `result.py` — leaf types: `ModerationSeverity`, `ModerationCategory`,
  `ModerationDirection`, `ModerationResult`, `ModerationProvider` protocol.
- `moderator.py` — `Moderator.check`, refusal and fallback text,
  `SafetyRejectedError`.
- `thresholds.py` — `ModerationThresholds` per category plus `exempt`.
- `factory.py` — `build_moderator(cfg)`: heuristic always, OpenAI when keyed,
  mature-content exemptions.
- `heuristic.py` — `HeuristicProvider` prompt-injection patterns.
- `openai_provider.py` — `OpenAIModerationProvider`, score buckets, wire
  category map.

# Local Rules

- Keep provider-specific moderation behind factory and provider seams.
- Do not weaken policy thresholds without an explicit decision.
- Test provider-independent behavior without live paid calls.

# Patterns

- New category: add a `ModerationCategory` value, a matching
  `ModerationThresholds` field, and a `safety_threshold_*` field on `Config`;
  `_thresholds_from_config` picks it up with no factory edit.
- Provider fan-out uses `asyncio.gather(return_exceptions=True)` in
  `_score_all`, so one outage cannot drop another provider's hit.
- Score mapping changes are proven against recorded responses in
  `tests/fixtures/moderation_scores.json`
  (`tests/test_safety_recorded_scores.py`).

# Anti-patterns

- Logging flagged text or raw provider errors; only category, severity and
  length may reach logs (`_log_flagged`;
  `docs/decisions/0006-content-safety-moderation-pipeline.md`).
- Mapping plain OpenAI `violence` to `VIOLENCE`; it blocked ordinary fights
  in production (#369, ADR-0006 amendment).
- Exempting anything beyond `VIOLENCE` and `SEXUAL` for mature content
  (`tests/test_safety_factory.py`).
- Reading SDK scores without `model_dump(by_alias=True)`; `sexual/minors` and
  `self-harm` silently went unenforced (#361;
  `tests/test_safety_openai_sdk_scores.py`).
- Letting an unknown severity name widen the gate; `_severity_from_name` falls
  back to the strict default.

# Related

- [Engine](/engine/AGENTS.md)
- [LLM](/llm/AGENTS.md)
- [Web interface](/interfaces/web/AGENTS.md)
