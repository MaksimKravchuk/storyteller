"""Pydantic schemas for LLM JSON and tool-call response validation.

These schemas wrap the raw LLM output with typed field access. The
action-routing schemas in :mod:`cast.schemas.action_plan` plug into
the Director's tool-call path (see :mod:`cast.director_tools`); the
other schemas here (actor, scene, chronicler, ...) participate in the
strict structured-outputs path implemented in
:meth:`cast.base_performer_class.BasePerformer._send_json`.
"""
