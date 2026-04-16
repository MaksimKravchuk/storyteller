"""JSON-safe serialisation helpers for :class:`ScenarioReport`.

Separated from :mod:`benchmarks.harness.runner` so the runner stays
focused on orchestration. :func:`dataclasses.asdict` handles the
scalar fields; the pydantic :class:`TurnOutputs` payloads need
``model_dump`` by hand, and :class:`PanelMember` is flattened here
too so the archive artefact is a plain JSON object end-to-end.
"""

from __future__ import annotations

from dataclasses import asdict

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._scores import PanelMember, ScenarioReport


def _panel_member_to_dict(member: PanelMember) -> dict[str, str]:
    """Render a :class:`PanelMember` as a JSON-safe dict."""
    return {"provider": member.provider, "model_id": member.model_id}


def _serialise_captured_turn(turn: CapturedTurn) -> dict:
    """Flatten a captured turn — ``TurnOutputs`` needs ``model_dump`` by hand."""
    return {
        "index": turn.index,
        "player_action": turn.player_action,
        "narration": turn.narration,
        "turn_outputs": turn.turn_outputs.model_dump(mode="json"),
        "duration_ms": turn.duration_ms,
    }


def report_to_serialisable(report: ScenarioReport) -> dict:
    """Convert a :class:`ScenarioReport` to a JSON-safe dict."""
    payload = asdict(report)
    payload["captured_turns"] = [_serialise_captured_turn(turn) for turn in report.captured_turns]
    payload["panel"] = [_panel_member_to_dict(member) for member in report.panel]
    return payload
