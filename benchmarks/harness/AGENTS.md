---
type: Component
title: Benchmark Harness
description: Scenario execution, judging, scoring, archiving, aggregation, and report rendering internals.
resource: benchmarks/harness/
tags: [benchmarks, harness, scoring]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/harness/`.

# Boundary

`benchmarks/harness/` owns scenario execution, capture, scoring, judging,
archiving, aggregation, and report rendering.

# Local Rules

- Keep typed report structures in [benchmark harness types](/benchmarks/harness/types/AGENTS.md).
- Preserve deterministic execution boundaries for regression comparison.
- Do not run paid judge panels without approval.

# Related

- [Benchmarks](/benchmarks/AGENTS.md)
- [Benchmark scenarios](/benchmarks/scenarios/AGENTS.md)

