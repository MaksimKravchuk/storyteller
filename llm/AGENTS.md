---
type: Component
title: LLM
description: Provider-agnostic client abstraction for OpenAI, Anthropic, OpenRouter, and DeepSeek model calls.
resource: llm/
tags: [llm, providers, clients]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `llm/`.

# Boundary

`llm/` owns provider-specific API clients, shared client contracts, provider
detection, and call logging.

# Local Rules

- Keep provider details behind the shared client interface used by [cast](/cast/AGENTS.md).
- Do not make paid or credentialed checks without Max's approval.
- Test retries, schema handling, and sanitization without live provider calls.

# Related

- [Prompts](/prompts/AGENTS.md)
- [Costs](/costs/AGENTS.md)

