"""Judge panel assembly — selects witness models from available API keys.

The benchmark harness scores every evidence-LLM element with a panel of
distinct LLMs ("witnesses") rather than a single grader. The panel is
drawn from a curated roster in :data:`DEFAULT_ROSTER`; each candidate is
kept only if its provider has an API key available in the supplied
:class:`Config`. The ordering of :data:`DEFAULT_ROSTER` is the natural
order the panel should fill — starting with the most capable models —
and the panel size is capped at :data:`DEFAULT_MAX_JUDGES`.

The panel is identical across elements in a run, which keeps per-element
scores comparable. The full panel (plus the reason any roster candidate
was skipped) is recorded in the run artefact.
"""

from __future__ import annotations

from dataclasses import dataclass

from benchmarks.harness.types._scores import PanelMember
from config import Config, get_api_key_for_provider
from defaults.models import AI_MODELS, ModelConfig

DEFAULT_MAX_JUDGES = 6


@dataclass(frozen=True)
class RosterCandidate:
    """One roster entry — a short alias plus its underlying ModelConfig."""

    alias: str
    config: ModelConfig


# Ordered roster of judge candidates. Keep this list in sync with the
# ``AI_MODELS`` registry so missing entries fail loudly at import time.
DEFAULT_ROSTER: tuple[RosterCandidate, ...] = (
    RosterCandidate(alias="opus", config=AI_MODELS.claude_opus),
    RosterCandidate(alias="sonnet", config=AI_MODELS.claude_sonnet),
    RosterCandidate(alias="haiku", config=AI_MODELS.claude_haiku),
    RosterCandidate(alias="gpt-5.4-max", config=AI_MODELS.gpt5_4_max),
    RosterCandidate(alias="gpt-5.4-mini", config=AI_MODELS.gpt5_4_mini),
    RosterCandidate(alias="gpt-5.4-nano", config=AI_MODELS.gpt5_4_nano),
)


@dataclass(frozen=True)
class PanelAssembly:
    """Outcome of panel assembly — the members plus per-skip reasons."""

    members: list[PanelMember]
    skipped: list[dict]


def _candidate_matches_override(candidate: RosterCandidate, override: str) -> bool:
    """Return True when the candidate matches ``override`` by alias or model id.

    Matching is case-insensitive so ``"Opus"`` and ``"CLAUDE-OPUS-4-6"``
    both pick the Anthropic Opus entry.
    """
    needle = override.strip().lower()
    return needle in {candidate.alias.lower(), candidate.config.model_id.lower()}


def _resolve_roster(overrides: list[str] | None) -> list[RosterCandidate]:
    """Return the ordered roster after applying optional overrides.

    When ``overrides`` is empty or ``None`` the default roster is
    returned. Otherwise each override is resolved to a roster candidate
    in the order the user supplied — unknown overrides raise
    ``ValueError`` so typos don't silently shrink the panel.
    """
    if not overrides:
        return list(DEFAULT_ROSTER)
    resolved: list[RosterCandidate] = []
    for override in overrides:
        matches = [cand for cand in DEFAULT_ROSTER if _candidate_matches_override(cand, override)]
        if not matches:
            raise ValueError("Unknown judge model: {0}".format(override))
        resolved.append(matches[0])
    return resolved


def assemble_panel(
    cfg: Config,
    *,
    overrides: list[str] | None = None,
    max_judges: int = DEFAULT_MAX_JUDGES,
) -> PanelAssembly:
    """Build the witness panel from the roster + available API keys.

    Each candidate is checked against ``cfg`` via
    :func:`config.get_api_key_for_provider`. Candidates without a key
    are skipped and recorded with a reason so the run artefact makes
    clear why the panel has fewer than ``max_judges`` members.
    """
    roster = _resolve_roster(overrides)
    members: list[PanelMember] = []
    skipped: list[dict] = []
    for candidate in roster:
        if len(members) >= max_judges:
            skipped.append(
                {
                    "alias": candidate.alias,
                    "provider": candidate.config.provider,
                    "model_id": candidate.config.model_id,
                    "reason": "panel cap reached (max_judges={0})".format(max_judges),
                },
            )
            continue
        api_key = get_api_key_for_provider(candidate.config.provider, cfg)
        if not api_key:
            skipped.append(
                {
                    "alias": candidate.alias,
                    "provider": candidate.config.provider,
                    "model_id": candidate.config.model_id,
                    "reason": "no {0} api key".format(candidate.config.provider),
                },
            )
            continue
        members.append(
            PanelMember(provider=candidate.config.provider, model_id=candidate.config.model_id),
        )
    return PanelAssembly(members=members, skipped=skipped)
