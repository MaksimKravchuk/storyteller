"""Deterministic narration benchmarks for the Storyteller engine.

The benchmark layer runs seeded scenarios against the engine's Python API,
records per-turn :class:`cast.schemas.turn_outputs.TurnOutputs` and GameState
snapshots, and scores pre-declared "elements" with a mix of deterministic
predicates and an evidence-citing LLM witness panel. Results are written to
``benchmarks/results/`` as timestamped JSON + markdown pairs for
release-over-release comparison.

Benchmarks are **opt-in**: they are excluded from the default pytest
gauntlet and must be invoked explicitly via ``uv run python -m benchmarks``.
"""
