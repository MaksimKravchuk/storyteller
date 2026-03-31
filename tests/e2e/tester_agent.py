"""TesterAgent — uses Claude to act as player and verify game outcomes."""

_MODEL = "claude-haiku-4-5-20251001"
_DECIDE_MAX_TOKENS = 20
_VERIFY_MAX_TOKENS = 5


class TesterAgent:
    def __init__(self):
        from anthropic import Anthropic

        self._client = Anthropic()
        self._model = _MODEL

    def decide_action(self, narration: str, goal: str) -> str:
        """Return a short player action (1-8 words) for the given goal."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=_DECIDE_MAX_TOKENS,
            system="Output ONLY a short player action (1-8 words). No explanation.",
            messages=[{"role": "user", "content": f"Scene:\n{narration}\n\nGoal: {goal}"}],
        )
        return response.content[0].text.strip()

    def verify(self, narration: str, condition: str) -> bool:
        """Return True if the narration satisfies the condition."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=_VERIFY_MAX_TOKENS,
            system="Answer ONLY with YES or NO.",
            messages=[{"role": "user", "content": f"Text:\n{narration}\n\nCondition: {condition}"}],
        )
        return response.content[0].text.strip().upper().startswith("YES")
