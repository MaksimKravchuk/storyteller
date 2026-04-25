"""Cell-level formatters for the comparison markdown."""

from __future__ import annotations

from benchmarks.model_sets._score import SetScore

_MISSING = "—"
_UNKNOWN = "?"
_DRAMATURGE_KEY = "dramaturge_enabled"
_FULL_ITERATIONS = 3


def format_score(score: SetScore | None) -> str:
    """Render the ``mean / base (n=…)`` cell, badging undersized iterations."""
    if score is None:
        return _MISSING
    badge = "" if score.iterations >= _FULL_ITERATIONS else " ⚠"
    return "{0:.2f} / {1} (n={2}){3}".format(score.mean, score.total_base, score.iterations, badge)


def format_iterations(score: SetScore | None) -> str:
    """Render the per-iteration totals tuple, or ``—`` when missing."""
    if score is None:
        return _MISSING
    return str(score.iteration_totals)


def _models_parts(models: dict[str, str]) -> list[str]:
    parts = [
        "director=`{0}`".format(models.get("director_model", _UNKNOWN)),
        "agent=`{0}`".format(models.get("agent_model", _UNKNOWN)),
        "narrator=`{0}`".format(models.get("narrator_model", _UNKNOWN)),
    ]
    if _DRAMATURGE_KEY in models:
        parts.append(
            "dramaturge=`{0}` (enabled={1})".format(
                models.get("dramaturge_model", _UNKNOWN),
                models.get(_DRAMATURGE_KEY, _UNKNOWN),
            ),
        )
    return parts


def format_models(score: SetScore | None) -> str:
    """Render the engine-models cell from a score's ``engine_models`` dict."""
    if score is None or not score.engine_models:
        return _MISSING
    return " ".join(_models_parts(score.engine_models))
