"""Per-category severity thresholds for the content-safety pipeline.

The dataclass field names mirror :class:`ModerationCategory` values exactly
(``violence`` / ``sexual_minors`` / etc.), so threshold lookup goes through
``getattr(self, category.value)`` and a new category never needs more than
one map entry to wire up. Operators override defaults via the
``safety_threshold_*`` fields on :class:`config.Config`.
"""

from __future__ import annotations

from dataclasses import dataclass

from safety.result import ModerationCategory, ModerationSeverity


@dataclass(frozen=True)
class ModerationThresholds:
    """Per-category severity thresholds.

    Defaults are tuned for historical text-quest narration: medium-severity
    violence (sword fights, sieges) passes, but explicit sexual content,
    minors, self-harm instructions, and prompt-injection attempts are gated.
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
        return getattr(self, category.value)

    def is_violation(self, category: ModerationCategory, severity: ModerationSeverity) -> bool:
        """Return True if ``severity`` meets or exceeds the configured threshold."""
        return severity >= self.threshold_for(category)
