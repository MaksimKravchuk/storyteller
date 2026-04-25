"""Per-set score model + builders from aggregate / iter JSON payloads."""

from __future__ import annotations

from dataclasses import dataclass

_ZERO = float(0)


@dataclass(frozen=True)
class SetScore:
    """A single (set, scenario) score, sourced from aggregate or per-iter JSONs."""

    iterations: int
    total_base: int
    iteration_totals: tuple[int, ...]
    engine_models: dict[str, str]

    @property
    def mean(self) -> float:
        if not self.iteration_totals:
            return _ZERO
        return sum(self.iteration_totals) / len(self.iteration_totals)


def from_aggregate(payload: dict, engine_models: dict[str, str]) -> SetScore:
    """Build a :class:`SetScore` from an aggregate JSON payload.

    ``engine_models`` is passed in because aggregate files do not carry it
    today (only per-iteration JSONs do); callers source it from a sibling
    iter file when available. Required payload keys (``iteration_totals``,
    ``total_base``) raise :class:`KeyError` if missing — silently
    substituting zero would mask a malformed archive as a bad score.
    """
    totals = tuple(payload["iteration_totals"])
    return SetScore(
        iterations=payload.get("iterations", len(totals)),
        total_base=payload["total_base"],
        iteration_totals=totals,
        engine_models=engine_models,
    )


def from_iters(iter_payloads: list[dict]) -> SetScore:
    """Build a :class:`SetScore` from one or more per-iteration JSON payloads.

    Required keys (``total_awarded`` per iter, ``total_base`` on the head)
    raise :class:`KeyError` rather than silently scoring 0.
    """
    totals = tuple(payload["total_awarded"] for payload in iter_payloads)
    head = iter_payloads[0]
    return SetScore(
        iterations=len(iter_payloads),
        total_base=head["total_base"],
        iteration_totals=totals,
        engine_models=head.get("engine_models", {}),
    )
