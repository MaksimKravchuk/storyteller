"""TesterAgent — uses Claude to act as player and verify game outcomes."""

import os

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_DECIDE_MAX_TOKENS = 20
_VERIFY_MAX_TOKENS = 5


class TesterAgent:
    def __init__(self):
        import anthropic

        self._client = anthropic.Anthropic()
        self._anthropic = anthropic
        self._model = os.environ.get("TESTER_AGENT_MODEL", _DEFAULT_MODEL)

    def decide_action(self, narration: str, goal: str) -> str:
        """Return a short player action (1-8 words) for the given goal."""
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_DECIDE_MAX_TOKENS,
                system="Output ONLY a short player action (1-8 words). No explanation.",
                messages=[{"role": "user", "content": f"Scene:\n{narration}\n\nGoal: {goal}"}],
            )
        except self._anthropic.APIStatusError as exc:
            raise RuntimeError(
                f"TesterAgent API error in decide_action (model={self._model}, status={exc.status_code})"
            ) from exc
        except self._anthropic.APIConnectionError as exc:
            raise RuntimeError("TesterAgent lost connection to Anthropic API") from exc
        action = response.content[0].text.strip()
        if not action:
            raise ValueError(f"TesterAgent returned empty action for goal={goal!r}")
        return action

    def verify(self, narration: str, condition: str) -> bool:
        """Return True if the narration satisfies the condition."""
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_VERIFY_MAX_TOKENS,
                system="Answer ONLY with YES or NO.",
                messages=[{"role": "user", "content": f"Text:\n{narration}\n\nCondition: {condition}"}],
            )
        except self._anthropic.APIStatusError as exc:
            raise RuntimeError(
                f"TesterAgent API error in verify (model={self._model}, status={exc.status_code})"
            ) from exc
        except self._anthropic.APIConnectionError as exc:
            raise RuntimeError("TesterAgent lost connection to Anthropic API") from exc
        answer = response.content[0].text.strip().upper()
        if not answer.startswith(("YES", "NO")):
            raise ValueError(f"TesterAgent returned unexpected verify response: {answer!r}")
        return answer.startswith("YES")
