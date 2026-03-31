"""TesterAgent — uses an LLM to act as player and verify game outcomes.

Prefers Anthropic (Claude) when ANTHROPIC_API_KEY is set; falls back to
OpenAI when only OPENAI_API_KEY is available.
"""

import os

_ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_OPENAI_DEFAULT_MODEL = "gpt-5.4-nano"
_DECIDE_MAX_TOKENS = 20
_VERIFY_MAX_TOKENS = 5


class TesterAgent:
    def __init__(self):
        if os.environ.get("ANTHROPIC_API_KEY"):
            self._backend = "anthropic"
            import anthropic

            self._client = anthropic.Anthropic()
            self._anthropic = anthropic
            self._model = os.environ.get("TESTER_AGENT_MODEL", _ANTHROPIC_DEFAULT_MODEL)
        elif os.environ.get("OPENAI_API_KEY"):
            self._backend = "openai"
            from openai import OpenAI

            self._client = OpenAI()
            self._model = os.environ.get("TESTER_AGENT_MODEL", _OPENAI_DEFAULT_MODEL)
        else:
            raise RuntimeError("TesterAgent requires ANTHROPIC_API_KEY or OPENAI_API_KEY")

    def decide_action(self, narration: str, goal: str) -> str:
        """Return a short player action (1-8 words) for the given goal."""
        action = self._chat(
            system="Output ONLY a short player action (1-8 words). No explanation.",
            user=f"Scene:\n{narration}\n\nGoal: {goal}",
            max_tokens=_DECIDE_MAX_TOKENS,
        )
        if not action:
            raise ValueError(f"TesterAgent returned empty action for goal={goal!r}")
        return action

    def verify(self, narration: str, condition: str) -> bool:
        """Return True if the narration satisfies the condition."""
        answer = self._chat(
            system="Answer ONLY with YES or NO.",
            user=f"Text:\n{narration}\n\nCondition: {condition}",
            max_tokens=_VERIFY_MAX_TOKENS,
        )
        if not answer.startswith(("YES", "NO")):
            raise ValueError(f"TesterAgent returned unexpected verify response: {answer!r}")
        return answer.startswith("YES")

    def _chat(self, *, system: str, user: str, max_tokens: int) -> str:
        if self._backend == "anthropic":
            return self._chat_anthropic(system=system, user=user, max_tokens=max_tokens)
        return self._chat_openai(system=system, user=user, max_tokens=max_tokens)

    def _chat_anthropic(self, *, system: str, user: str, max_tokens: int) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except self._anthropic.APIStatusError as exc:
            raise RuntimeError(f"TesterAgent API error (model={self._model}, status={exc.status_code})") from exc
        except self._anthropic.APIConnectionError as exc:
            raise RuntimeError("TesterAgent lost connection to Anthropic API") from exc
        return response.content[0].text.strip()

    def _chat_openai(self, *, system: str, user: str, max_tokens: int) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.choices[0].message.content or "").strip()
