---
type: Component
title: Engine
description: Public GameEngine API and wiring layer that connects models, cast agents, timeline, knowledge, and persistence.
resource: engine/
tags: [engine, runtime, wiring]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `engine/`.

# Boundary

`engine/` owns the public `GameEngine` API, factory/wiring code, turn lifecycle,
session restoration, the moderation seam, and persistence handoff. It does not
own agent behavior ([cast](/cast/AGENTS.md)), moderation policy
([safety](/safety/AGENTS.md)), or SQL ([db](/db/AGENTS.md)).

# Contents

- `game_engine.py` — `GameEngine`: `start_game`, `process_action`,
  `restore_session`, `assert_running`; hides the synthetic opening prompt.
- `factory.py` — `create_engine` (config → engine, role overrides, benchmark
  `temperature_override`) and `create_engine_from_state`.
- `engine_wiring.py` — `create_llm_clients`, `wire_director`, `restore_actors`.
- `session_ops.py` — `begin_session`, `resume_session`, `persist_engine_state`
  and per-turn buffer binding; `session_restore.py` restores with admin settings.
- `model_overrides.py`, `search_settings.py` — read admin-panel overrides from
  `admin_settings` into `ModelConfig` / `SearchSettings`.
- `moderation.py` — `moderate_input`, `moderate_narration`, `SentenceGate`.
- `graph_populator.py`, `location_init.py` — seed the knowledge graph and
  `Location`s from the researched `Setting`.

# Local Rules

- Keep orchestration in the engine and agent behavior in [cast](/cast/AGENTS.md).
- Preserve persistence boundaries with [db](/db/AGENTS.md).
- Changes to turn flow, player-facing behavior, or narrative paths need
  consumer-side tests and may need benchmark evidence.
- Web flows enter through `session_ops.py`, not by calling `create_engine`
  directly, so buffers are bound and admin overrides apply.

# Patterns

- New engine-level config: thread it through `create_engine` in `factory.py`
  as a keyword argument, like `search_override`.
- Resume paths call `restore_engine_with_admin_settings` so restored games
  follow the current admin model and search choice (#385).
- Per-turn telemetry rides ContextVar buffers reset in `_bind_session_buffers`
  and flushed in `persist_engine_state`.
- Moderation stays at the engine seam: `process_action` wraps
  `director.execute` in `moderate_narration`; the web layer only maps
  `SafetyRejectedError` to HTTP.

# Anti-patterns

- Moving `_flush_reliability_snapshot` after `get_and_clear_events` drops the
  snapshot (`docs/decisions/0002-reliability-metering-via-turn-events-payload.md`;
  `tests/test_session_ops_reliability.py`).
- Passing `temperature_override` from production code or adding it to
  `create_engine_from_state`; it is benchmark-only
  (`docs/decisions/0003-engine-temperature-pinning-in-benchmark-mode.md`).
- Moderating in a client or route instead of `process_action`, or releasing
  streamed prose before `SentenceGate` checks it
  (`docs/decisions/0006-content-safety-moderation-pipeline.md`,
  `docs/decisions/0022-stream-narrator-prose-over-sse.md`;
  `tests/test_turn_stream.py`).
- Letting the opening turn run NPC dialogue or leak the synthetic prompt into
  player history (`docs/decisions/0007-opening-turn-build-and-narrate-only.md`;
  `tests/test_game_engine_lifecycle.py`).

# Related

- [Knowledge](/knowledge/AGENTS.md)
- [Timeline](/timeline/AGENTS.md)
- [Interfaces](/interfaces/AGENTS.md)
- [Safety](/safety/AGENTS.md)
