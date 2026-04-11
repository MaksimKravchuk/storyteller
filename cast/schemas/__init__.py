"""Pydantic schemas for LLM JSON response validation.

These schemas wrap the raw ``_send_json`` output with typed field
access and participate in the self-correcting validation-retry loop
implemented in :meth:`cast.base_performer_class.BasePerformer._send_json`.
They are purely a parse/validate layer — domain models (``NPCCard``,
``Setting``, ``Scene``) remain dataclasses in this step and are
constructed from the validated schema instances in the generator
callers.

TODO(step-2): The routing response (``cast/director_routing.py``) is
intentionally NOT schema-validated in this step. Modelling it cleanly
requires touching ``director.py``, ``director_execution.py``,
``wait_detection.build_forced_wait_plan`` (which returns a plain
dict), and ``ActionRouter.save_pending_clarification`` (which persists
the dict via ``json.dumps``). The consumers all use ``plan.get(...)``
and the forced-wait path bypasses the LLM entirely, so a partial
migration would leave the routing surface half-typed. Tracked as a
follow-up after the domain-model migration (step 3) lands.
"""
