"""Judge panel assembly — selects witness models from available API keys."""

from __future__ import annotations

from dataclasses import dataclass

from benchmarks.harness.types._scores import PanelMember, SkippedCandidate
from config import Config, get_api_key_for_provider
from defaults.models import AI_MODELS, ModelConfig

DEFAULT_MAX_JUDGES = 6


@dataclass(frozen=True)
class RosterCandidate:
    """One roster entry — a short alias plus its underlying ModelConfig."""

    alias: str
    config: ModelConfig


# Keep in sync with ``AI_MODELS`` so missing entries fail loudly at import.
DEFAULT_ROSTER: tuple[RosterCandidate, ...] = (
    RosterCandidate(alias="opus", config=AI_MODELS.claude_opus),
    RosterCandidate(alias="sonnet", config=AI_MODELS.claude_sonnet),
    RosterCandidate(alias="haiku", config=AI_MODELS.claude_haiku),
    RosterCandidate(alias="gpt-6-astra", config=AI_MODELS.gpt6_astra),
    RosterCandidate(alias="gpt-6.1-sol", config=AI_MODELS.gpt6_1_sol),
    RosterCandidate(alias="gpt-6-luna", config=AI_MODELS.gpt6_luna),
)


@dataclass(frozen=True)
class PanelAssembly:
    """Outcome of panel assembly — the members plus per-skip reasons."""

    members: list[PanelMember]
    skipped: list[SkippedCandidate]


def _candidate_matches_override(candidate: RosterCandidate, override: str) -> bool:
    """Return True when the candidate matches ``override`` by alias or model id."""
    needle = override.strip().lower()
    return needle in {candidate.alias.lower(), candidate.config.model_id.lower()}


def _resolve_roster(overrides: list[str] | None) -> list[RosterCandidate]:
    """Return the ordered roster after applying optional overrides."""
    if not overrides:
        return list(DEFAULT_ROSTER)
    resolved: list[RosterCandidate] = []
    for override in overrides:
        matches = [cand for cand in DEFAULT_ROSTER if _candidate_matches_override(cand, override)]
        if not matches:
            raise ValueError("Unknown judge model: {0}".format(override))
        resolved.append(matches[0])
    return resolved


def _skip_for(candidate: RosterCandidate, reason: str) -> SkippedCandidate:
    """Build a :class:`SkippedCandidate` for a rejected roster entry."""
    return SkippedCandidate(
        alias=candidate.alias,
        provider=candidate.config.provider,
        model_id=candidate.config.model_id,
        reason=reason,
    )


def assemble_panel(
    cfg: Config,
    *,
    overrides: list[str] | None = None,
    max_judges: int = DEFAULT_MAX_JUDGES,
) -> PanelAssembly:
    """Build the witness panel from the roster + available API keys."""
    roster = _resolve_roster(overrides)
    members: list[PanelMember] = []
    skipped: list[SkippedCandidate] = []
    for candidate in roster:
        if len(members) >= max_judges:
            skipped.append(_skip_for(candidate, "panel cap reached (max_judges={0})".format(max_judges)))
            continue
        api_key = get_api_key_for_provider(candidate.config.provider, cfg)
        if not api_key:
            skipped.append(_skip_for(candidate, "no {0} api key".format(candidate.config.provider)))
            continue
        members.append(
            PanelMember(provider=candidate.config.provider, model_id=candidate.config.model_id),
        )
    return PanelAssembly(members=members, skipped=skipped)
