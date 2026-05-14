"""Per-category severity thresholds for the content-safety pipeline."""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import dataclass

from safety.result import ModerationCategory, ModerationSeverity


@dataclass(frozen=True)
class ModerationThresholds:
    """Per-category severity thresholds.

    Defaults are tuned for historical text-quest narration: medium-severity
    violence (sword fights, sieges) passes, but explicit sexual content,
    minors, self-harm instructions, and prompt-injection attempts are gated.
    Override values via env vars — see :func:`safety.factory.build_moderator`.
    """

    violence: ModerationSeverity = ModerationSeverity.HIGH
    sexual: ModerationSeverity = ModerationSeverity.HIGH
    sexual_minors: ModerationSeverity = ModerationSeverity.LOW
    harassment: ModerationSeverity = ModerationSeverity.HIGH
    hate: ModerationSeverity = ModerationSeverity.MEDIUM
    self_harm: ModerationSeverity = ModerationSeverity.MEDIUM
    illicit: ModerationSeverity = ModerationSeverity.HIGH
    prompt_injection: ModerationSeverity = ModerationSeverity.MEDIUM

    def threshold_for(self, category: ModerationCategory) -> ModerationSeverity:
        """Return the configured severity threshold for ``category``."""
        return getattr(self, _THRESHOLD_FIELD_NAMES[category])

    def is_violation(self, category: ModerationCategory, severity: ModerationSeverity) -> bool:
        """Return True if ``severity`` meets or exceeds the configured threshold."""
        return severity >= self.threshold_for(category)


_THRESHOLD_FIELD_NAMES: Mapping[ModerationCategory, str] = types.MappingProxyType(
    {
        ModerationCategory.VIOLENCE: "violence",
        ModerationCategory.SEXUAL: "sexual",
        ModerationCategory.SEXUAL_MINORS: "sexual_minors",
        ModerationCategory.HARASSMENT: "harassment",
        ModerationCategory.HATE: "hate",
        ModerationCategory.SELF_HARM: "self_harm",
        ModerationCategory.ILLICIT: "illicit",
        ModerationCategory.PROMPT_INJECTION: "prompt_injection",
    },
)
