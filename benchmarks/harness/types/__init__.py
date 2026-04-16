"""Core data types shared across the benchmark harness.

The type surface is split across the ``_elements``, ``_scenarios``,
``_captures``, and ``_scores`` submodules. Callers should import from
the specific submodule — for example:

    from benchmarks.harness.types._scores import ScenarioReport
    from benchmarks.harness.types._elements import Element, ElementKind

This package root is intentionally empty because the project convention
is to keep package roots logic-free.
"""
