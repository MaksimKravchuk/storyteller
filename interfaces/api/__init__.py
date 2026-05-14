"""HTTP/SSE API wrapping the agent engine for mobile/native clients.

This package is deliberately separate from ``interfaces.web``:

- ``interfaces.web`` is a stateful, cookie-tracked, DB-persisted UI that
  serves a single-page browser app and stores state via
  ``GameRepository``.
- ``interfaces.api`` is a small in-memory wrapper over ``GameEngine``
  for mobile clients to drive over HTTP/SSE. There is no persistence,
  no auth, no rate limiting — sessions live in process memory and
  vanish on restart.
"""
