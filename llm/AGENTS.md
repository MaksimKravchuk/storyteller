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

`llm/` owns provider-specific API clients, shared client contracts, client
construction, and call logging. Provider detection from the model name lives
in `config.py` (`_detect_provider`); prompts, retries on bad JSON content and
performer logic live in [cast](/cast/AGENTS.md).

# Contents

- `base_client.py` — `BaseLLMClient` (`send_message`, default one-chunk
  `stream_message`) and `LLMJSONError`.
- `message.py` — `Message`, `Role`, `Tool`, `ToolCall`, `OutputFormat`,
  `LLMResponse`: the provider-neutral wire types.
- `openai_client.py` (+ `_openai_tools.py` strict-schema and tool wiring) —
  also serves OpenRouter and DeepSeek via `base_url`.
- `anthropic_client.py` (+ `_anthropic_schema.py` schema hardening).
- `factory.py` — `create_llm_client(ModelConfig)` picks the client and
  caches it per process and event loop (`_cached_client`).
- `retry.py` — `call_with_retry`, the one shared retry loop with backoff.
- `image_client.py` — poster image generation only (ADR-0020).
- ContextVar turn buffers: `call_logger.py` (AI call log), `turn_event_logger.py`
  (typed turn events), `turn_stream.py` (live stage/delta sink, ADR-0022).

# Local Rules

- Keep provider details behind the shared client interface used by [cast](/cast/AGENTS.md).
- Do not make paid or credentialed checks without Max's approval.
- Test retries, schema handling, and sanitization without live provider calls.
- Model-specific wire quirks are keyed by model-id prefix tuples, e.g.
  `_REASONING_NONE_MODEL_PREFIXES` (ADR-0018, ADR-0019).

# Patterns

- Strict output a provider cannot honour raises `NotImplementedError` so
  `BasePerformer._send_json` falls back to prompt JSON; see
  `AnthropicClient._guard_strict_supported` and its schema quarantine.
- Retries live in one app layer, `llm.retry.call_with_retry`; each client
  only names its retryable exceptions in a thin `_call_with_retry`. SDK
  clients get explicit `_REQUEST_TIMEOUT_S` and `max_retries=0` (#362).
- Per-turn state uses a module `ContextVar` that is a no-op when unbound
  (`turn_stream.py`, `call_logger.call_log_buffer`).
- Import provider SDKs lazily inside the factory branch or client, as
  `factory.py` and `image_client.py` do.
- A test fake that subclasses `BaseLLMClient` gets `stream_message` for free
  (`tests/test_narrator_streaming.py`).

# Anti-patterns

- Re-enabling SDK retries or the 600 s default timeout; retries multiply
  and turns hang (#362, guarded by `tests/test_llm_timeouts.py`).
- Retrying a half-sent stream; only the stream opening is retried
  (`docs/decisions/0022-stream-narrator-prose-over-sse.md`,
  `tests/test_llm_streaming.py`).
- Sending raw Pydantic schemas: OpenAI needs `_StrictSchemaNormalizer`,
  Anthropic needs `harden_anthropic_schema` (`tests/test_strict_schema_regression.py`,
  `tests/test_anthropic_schema.py`).
- Sending `reasoning_effort` to every model; only listed prefixes get it so
  other wire payloads stay unchanged
  (`docs/decisions/0018-default-agent-roles-to-gpt-6-luna.md`).
- Skipping `_sanitize` on OpenAI message bodies; lone surrogates and control
  characters break the request.

# Related

- [Prompts](/prompts/AGENTS.md)
- [Costs](/costs/AGENTS.md)
- [Cast](/cast/AGENTS.md)
