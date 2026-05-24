"""Spend report construction from aggregated AI call usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from config import Config
from costs.model_pricing import CallCost, calculate_call_cost_usd


class _Fields:
    """Stable JSON field names used by cost reports."""

    cost = "estimated_cost_usd"
    call_count = "call_count"
    prompt_tokens = "prompt_tokens"
    completion_tokens = "completion_tokens"
    missing_usage = "missing_usage_count"
    unpriced_count = "unpriced_call_count"
    model = "model"
    total_tokens = "total_tokens"


def _money(money_amount: Decimal) -> str:
    """Render Decimal money values for stable JSON responses."""
    return format(money_amount.quantize(Decimal("0.000001")), "f")


@dataclass
class _ReportTotals:
    """Mutable counters for the full cost summary."""

    cost: Decimal = Decimal("0")
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    missing_usage: int = 0
    unpriced_calls: int = 0

    def add(self, row_cost: Decimal, row: "_UsageRow", *, unpriced: bool) -> None:
        """Accumulate one usage row into the totals."""
        self.cost += row_cost
        self.calls += row.call_count
        self.prompt_tokens += row.prompt_tokens
        self.completion_tokens += row.completion_tokens
        self.missing_usage += row.missing_usage_count
        if unpriced:
            self.unpriced_calls += row.call_count

    def payload(self) -> dict[str, Any]:
        """Return JSON-friendly total fields."""
        return {
            _Fields.cost: _money(self.cost),
            _Fields.call_count: self.calls,
            _Fields.prompt_tokens: self.prompt_tokens,
            _Fields.completion_tokens: self.completion_tokens,
            _Fields.total_tokens: self.prompt_tokens + self.completion_tokens,
            _Fields.missing_usage: self.missing_usage,
            _Fields.unpriced_count: self.unpriced_calls,
        }


@dataclass(frozen=True)
class _UsageRow:
    """Typed view over aggregate AI usage rows."""

    source: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    call_count: int
    missing_usage_count: int

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> "_UsageRow":
        """Build a typed row from the repository aggregate mapping."""
        return cls(
            source=row,
            prompt_tokens=int(row.get(_Fields.prompt_tokens) or 0),
            completion_tokens=int(row.get(_Fields.completion_tokens) or 0),
            call_count=int(row.get(_Fields.call_count) or 0),
            missing_usage_count=int(row.get(_Fields.missing_usage) or 0),
        )

    def payload(self, row_cost: Decimal, *, unpriced: bool) -> dict[str, Any]:
        """Return a JSON-friendly row payload."""
        return {
            "user_id": self.source.get("user_id"),
            "session_id": self.source.get("session_id"),
            "game_state_id": self.source.get("game_state_id"),
            "utc_day": self.source.get("utc_day"),
            _Fields.model: self.source.get(_Fields.model),
            _Fields.prompt_tokens: self.prompt_tokens,
            _Fields.completion_tokens: self.completion_tokens,
            _Fields.total_tokens: self.prompt_tokens + self.completion_tokens,
            _Fields.call_count: self.call_count,
            _Fields.cost: _money(row_cost),
            "unpriced": unpriced,
            _Fields.missing_usage: self.missing_usage_count,
            "started_at": self.source.get("started_at"),
            "ended_at": self.source.get("ended_at"),
        }


@dataclass
class _ReportAccumulator:
    """Accumulates row, user, model, and total cost summary data."""

    total: _ReportTotals = field(default_factory=_ReportTotals)
    by_user: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_model: dict[str, dict[str, Any]] = field(default_factory=dict)
    report_rows: list[dict[str, Any]] = field(default_factory=list)

    def add(self, row: _UsageRow, cfg: Config) -> None:
        """Add one aggregate row to every report section."""
        call_cost = calculate_call_cost_usd(
            row.source.get(_Fields.model),
            row.prompt_tokens,
            row.completion_tokens,
            cfg,
        )
        self.total.add(call_cost.cost_usd, row, unpriced=call_cost.unpriced)
        self._add_grouped_rows(row, call_cost)
        self.report_rows.append(row.payload(call_cost.cost_usd, unpriced=call_cost.unpriced))

    def _add_grouped_rows(self, row: _UsageRow, call_cost: CallCost) -> None:
        """Add one row to user and model grouped report buckets."""
        user_key = str(row.source.get("user_id") or "unattributed")
        model_key = str(row.source.get(_Fields.model) or "unknown")
        self._add_bucket(self.by_user, user_key, row, call_cost)
        self._add_bucket(self.by_model, model_key, row, call_cost)

    def _add_bucket(
        self,
        bucket: dict[str, dict[str, Any]],
        bucket_key: str,
        row: _UsageRow,
        call_cost: CallCost,
    ) -> None:
        """Add one row to a grouped report bucket."""
        entry = bucket.setdefault(bucket_key, self._empty_bucket())
        entry[_Fields.cost] += call_cost.cost_usd
        entry[_Fields.call_count] += row.call_count
        entry[_Fields.prompt_tokens] += row.prompt_tokens
        entry[_Fields.completion_tokens] += row.completion_tokens
        entry[_Fields.missing_usage] += row.missing_usage_count
        if call_cost.unpriced:
            entry[_Fields.unpriced_count] += row.call_count

    def _empty_bucket(self) -> dict[str, Any]:
        """Return a fresh grouped report bucket."""
        return {
            _Fields.cost: Decimal("0"),
            _Fields.call_count: 0,
            _Fields.prompt_tokens: 0,
            _Fields.completion_tokens: 0,
            _Fields.missing_usage: 0,
            _Fields.unpriced_count: 0,
        }


def build_cost_summary(rows: list, cfg: Config) -> dict[str, Any]:
    """Build a prompt-free cost summary from usage aggregate rows."""
    accumulator = _ReportAccumulator()
    for row in rows:
        accumulator.add(_UsageRow.from_mapping(row), cfg)
    return {
        "total": accumulator.total.payload(),
        "by_user": _serialise_buckets(accumulator.by_user),
        "by_model": _serialise_buckets(accumulator.by_model),
        "rows": accumulator.report_rows,
    }


def _serialise_buckets(buckets: dict) -> list[dict[str, Any]]:
    """Convert internal Decimal bucket maps into JSON-friendly lists."""
    serialised = []
    for bucket_key, entry in sorted(buckets.items()):
        payload = dict(entry)
        payload["key"] = bucket_key
        payload[_Fields.cost] = _money(payload[_Fields.cost])
        serialised.append(payload)
    return serialised
