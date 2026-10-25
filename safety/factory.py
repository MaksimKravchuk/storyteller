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

from loguru import logger

from safety.heuristic import HeuristicProvider
from safety.moderator import Moderator
from safety.openai_provider import OpenAIModerationProvider
from safety.result import ModerationCategory, ModerationProvider, ModerationSeverity
from safety.thresholds import ModerationThresholds

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


_MATURE_CATEGORIES = frozenset((ModerationCategory.VIOLENCE, ModerationCategory.SEXUAL))


def _thresholds_from_config(cfg: "Config") -> ModerationThresholds:
    """Translate the env-derived threshold names into a :class:`ModerationThresholds`.

    Drives off :class:`ModerationCategory` so a new category needs only an
    enum entry, a matching dataclass field, and a ``safety_threshold_*``
    field on :class:`Config` — not a factory edit.
    """
    overrides = {
        category.value: _severity_from_name(
            getattr(cfg, "safety_threshold_{0}".format(category.value)),
            category.value,
        )
        for category in ModerationCategory
    }
    exempt = _MATURE_CATEGORIES if cfg.safety_mature_content else frozenset()
    return ModerationThresholds(**overrides, exempt=exempt)


def _severity_from_name(name: str, field_name: str) -> ModerationSeverity:
    """Look up a :class:`ModerationSeverity` by case-insensitive name.

    Falls back to the dataclass default for ``field_name`` if ``name``
    doesn't match a known severity — a typo never silently widens the
    moderation gate — and logs the misconfiguration so operators notice
    instead of silently keeping the strict default.
    """
    try:
        return ModerationSeverity[name.strip().upper()]
    except KeyError:
        default = getattr(ModerationThresholds(), field_name)
        logger.warning(
            "content_safety.threshold_invalid field={} value={!r} falling_back_to={}",
            field_name,
            name,
            default.name,
        )
        return default
