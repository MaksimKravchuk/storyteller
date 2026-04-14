"""Narrative Test Agent — higher-tier QA reviewer for the game's narrative.

The Narrative Test Agent audits an active :class:`models.game_state.GameState`
snapshot and returns a :class:`NarrativeEvaluation` that scores six narrative
dimensions: story, turns, scenes, confrontation, memory, and autonomy.

The agent is intentionally out-of-band:

- It never mutates ``GameState`` or any other engine data.
- It is NOT wired into the per-turn Director pipeline.
- It expects to be backed by a higher-tier model (Claude Sonnet by default)
  because its review quality depends on the reviewer's narrative judgement.

Callers build it via :func:`engine.factory.create_narrative_test_agent`,
which reads the ``narrative_test_model`` field from :class:`config.Config`
and instantiates the appropriate LLM client.

The prompt-assembly helpers live in :mod:`cast.narrative_test_formatters`
so this module can stay focused on the :class:`NarrativeTestAgent` class.
"""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from cast.narrative_test_formatters import build_audit_kwargs
from cast.schemas.narrative_test_response import NarrativeEvaluation
from models.game_state import GameState
from prompts.narrative_test_prompts import NARRATIVE_TEST_AUDIT, NARRATIVE_TEST_SYSTEM


class NarrativeTestAgent(BasePerformer):
    """Higher-tier reviewer that audits the game's narrative health.

    The agent scores six dimensions (story, turns, scenes, confrontation,
    memory, autonomy) and returns a :class:`NarrativeEvaluation`. It is
    consulted out-of-band — never wired into the per-turn pipeline — and
    reads the provided :class:`GameState` without mutating it.
    """

    def __init__(self, *, llm_client: Any):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=NARRATIVE_TEST_SYSTEM,
        )

    async def act(self, input_data: GameState, context: dict) -> NarrativeEvaluation:
        """Audit a game snapshot and return a scored evaluation.

        ``input_data``: Live :class:`GameState`. Read-only — never mutated.

        ``context`` is optional and may contain:

        - ``confrontation_log``: list[str] of human-readable contest/combat lines.
        - ``autonomy_log``: list[str] of human-readable NPC-turn / departure lines.

        Both logs are optional because the engine currently does not persist
        them on ``GameState``; callers that care about those dimensions can
        assemble the lines themselves from whatever source is available
        (e.g. admin dashboard call logs, director retaliation records).
        """
        self.set_context(
            setting_name=input_data.setting.name,
            time_period=input_data.setting.time_period,
        )
        prompt = NARRATIVE_TEST_AUDIT.render(**build_audit_kwargs(input_data, context))
        return await self._send_json(prompt, response_model=NarrativeEvaluation)
