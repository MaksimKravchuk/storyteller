---
type: Component
title: Benchmarks
description: Deterministic narration-quality benchmark harness, scenarios, model panels, and comparison tooling.
resource: benchmarks/
tags: [benchmarks, evaluation, narrative-quality]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/`.

# Boundary

`benchmarks/` owns deterministic narrative-quality scenarios, harness execution,
judging, scoring, comparison, and result archiving.

# Local Rules

- Benchmark runs can hit paid LLM APIs; run them only after approval.
- Scenario changes should include a release-relevant rubric run when approved.
- Keep CLI behavior coordinated with [benchmark CLI](/benchmarks/cli/AGENTS.md)
  and execution internals in [benchmark harness](/benchmarks/harness/AGENTS.md).

# Related

- [Cast](/cast/AGENTS.md)
- [Engine](/engine/AGENTS.md)
- [Prompts](/prompts/AGENTS.md)

