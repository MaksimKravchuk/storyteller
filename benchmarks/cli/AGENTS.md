---
type: Component
title: Benchmark CLI
description: Command-line entry points for running, comparing, calibrating, pinning, and reporting benchmark outputs.
resource: benchmarks/cli/
tags: [benchmarks, cli, evaluation]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `benchmarks/cli/`.

# Boundary

`benchmarks/cli/` owns argument parsing and command dispatch for benchmark
workflows.

# Local Rules

- Keep CLI parsing separate from scoring and execution internals.
- Add tests for command dispatch, output formatting, and error paths.

# Related

- [Benchmarks](/benchmarks/AGENTS.md)
- [Benchmark harness](/benchmarks/harness/AGENTS.md)

