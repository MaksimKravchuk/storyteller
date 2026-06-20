---
type: Component
title: Benchmark Harness Types
description: Typed benchmark reports, captures, scenario definitions, scores, and aggregate structures.
resource: benchmarks/harness/types/
tags: [benchmarks, types, reports]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/harness/types/`.

# Boundary

`benchmarks/harness/types/` owns typed benchmark report, capture, scenario,
score, and aggregate structures.

# Local Rules

- Coordinate type changes with archive serialization and report rendering.
- Add tests for backward-compatible archive reads when shape changes.

# Related

- [Benchmark harness](/benchmarks/harness/AGENTS.md)
- [Models](/models/AGENTS.md)

