"""Re-record real omni-moderation scores for ``moderation_scores.json``.

Run when the moderation model changes: ``OPENAI_API_KEY=... uv run python tests/fixtures/record_moderation_scores.py``.
The moderation endpoint is free. Only ``category_scores`` and ``model`` are rewritten.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

FIXTURE = Path(__file__).with_name("moderation_scores.json")


def _score(samples: list[dict[str, Any]]) -> str:
    """Write fresh wire scores into ``samples`` in place; return the model that scored them."""
    texts = [row["text"] for row in samples]
    response = OpenAI().moderations.create(model="omni-moderation-latest", input=texts)
    for row, scored in zip(samples, response.results, strict=True):
        row["category_scores"] = scored.category_scores.model_dump(by_alias=True)
    return response.model


def main() -> None:
    """Score every sample text and write the raw wire scores back to the fixture."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["model"] = _score(fixture["samples"])
    dumped = json.dumps(fixture, ensure_ascii=False, indent=2)
    FIXTURE.write_text(f"{dumped}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
