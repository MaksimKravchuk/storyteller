"""Build a :class:`Moderator` from application config.

Wiring rules:

* :class:`HeuristicProvider` is always installed — it is cheap, has
  no dependencies, and catches prompt-injection patterns that the
  OpenAI endpoint does not surface.
* :class:`OpenAIModerationProvider` is added when an OpenAI API key
  is configured. Without an API key, the heuristic provider alone
  still catches prompt-injection — the moderator is never silently
  disabled.
* :data:`Config.safety_enabled` lets operators turn the whole pipeline
  off (returns ``None``); the engine treats ``None`` as "no moderation"
  and skips all checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from safety.heuristic import HeuristicProvider
from safety.moderator import Moderator
from safety.openai_provider import OpenAIModerationProvider
from safety.result import ModerationProvider, ModerationSeverity
from safety.thresholds import _THRESHOLD_FIELD_NAMES, ModerationThresholds

if TYPE_CHECKING:
    from config import Config


def build_moderator(cfg: "Config") -> Moderator | None:
    """Construct a :class:`Moderator` from the application config.

    Returns ``None`` when ``cfg.safety_enabled`` is False so the engine
    can skip every moderation call site without conditional wiring.
    """
    if not cfg.safety_enabled:
        return None
    providers: list[ModerationProvider] = [HeuristicProvider()]
    if cfg.openai_api_key:
        providers.append(OpenAIModerationProvider(api_key=cfg.openai_api_key))
    return Moderator(providers=providers, thresholds=_thresholds_from_config(cfg))


def _thresholds_from_config(cfg: "Config") -> ModerationThresholds:
    """Translate the env-derived threshold names into a :class:`ModerationThresholds`.

    Drives off ``_THRESHOLD_FIELD_NAMES`` so adding a new category requires
    touching only that map plus the matching ``safety_threshold_*`` field
    on :class:`Config` — not this factory.
    """
    overrides = {
        field_name: _severity_from_name(getattr(cfg, "safety_threshold_{0}".format(field_name)), field_name)
        for field_name in _THRESHOLD_FIELD_NAMES.values()
    }
    return ModerationThresholds(**overrides)


def _severity_from_name(name: str, field_name: str) -> ModerationSeverity:
    """Look up a :class:`ModerationSeverity` by case-insensitive name.

    Falls back to the dataclass default for ``field_name`` if ``name``
    doesn't match a known severity — a typo never silently widens the
    moderation gate.
    """
    try:
        return ModerationSeverity[name.strip().upper()]
    except KeyError:
        return getattr(ModerationThresholds(), field_name)
