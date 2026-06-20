---
type: Component
title: Benchmark Scenarios
description: Deterministic scenario definitions, scripts, expected elements, and seeded states for narrative-quality checks.
resource: benchmarks/scenarios/
tags: [benchmarks, scenarios, evaluation]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/scenarios/`.

# Boundary

`benchmarks/scenarios/` owns deterministic benchmark scenario packages.

# Local Rules

- Each scenario should keep state, script, expected elements, and scenario
  registration explicit.
- Release-relevant scenario additions need an approved run and rubric output.
- Keep shared scenario helpers generic and deterministic.

# Related

- [Benchmarks](/benchmarks/AGENTS.md)
- [Benchmark harness](/benchmarks/harness/AGENTS.md)

