"""Plain-text table rendering for the ``reliability-report`` CLI.

Kept separate from the command/aggregation module so that file's
member + complexity budgets stay well under the WPS caps.
"""

from __future__ import annotations

from dataclasses import dataclass

_AGENT_COL_HEADER = "agent"
_EVENT_COL_HEADER = "event_type"
_COUNT_COL_HEADER = "count"
_TABLE_PADDING = 2
_EMPTY_LINE = "(no reliability counters found)"


@dataclass(frozen=True)
class _TableRow:
    """One displayable row: ``(agent, event_type, count)`` already stringified."""

    agent: str
    event: str
    count: str


@dataclass(frozen=True)
class _ColumnWidths:
    """Cached padded-column widths for a single render."""

    agent: int
    event: int
    count: int


def format_table(counters: dict[tuple[str, str], int]) -> str:
    """Render the per-``(agent, event_type)`` counter table as a string."""
    if not counters:
        return _EMPTY_LINE
    rows = _rows_from_counters(counters)
    widths = _column_widths(rows)
    header_row = _TableRow(agent=_AGENT_COL_HEADER, event=_EVENT_COL_HEADER, count=_COUNT_COL_HEADER)
    separator_row = _TableRow(
        agent="-" * widths.agent,
        event="-" * widths.event,
        count="-" * widths.count,
    )
    lines = [_format_row(header_row, widths), _format_row(separator_row, widths)]
    lines.extend(_format_row(row, widths) for row in rows)
    return "\n".join(lines)


def _rows_from_counters(counters: dict[tuple[str, str], int]) -> list[_TableRow]:
    """Sort and stringify counters into displayable rows."""
    out: list[_TableRow] = []
    for key, count in sorted(counters.items()):
        agent, event_type = key
        out.append(_TableRow(agent=agent, event=event_type, count=str(count)))
    return out


def _max_width(header: str, rows: list[_TableRow], pick: str) -> int:
    """Return the largest cell width in attribute ``pick``, including the header."""
    candidates = [len(header)]
    candidates.extend(len(getattr(row, pick)) for row in rows)
    return max(candidates)


def _column_widths(rows: list[_TableRow]) -> _ColumnWidths:
    """Pick column widths that fit headers and every row."""
    return _ColumnWidths(
        agent=_max_width(_AGENT_COL_HEADER, rows, "agent"),
        event=_max_width(_EVENT_COL_HEADER, rows, "event"),
        count=_max_width(_COUNT_COL_HEADER, rows, "count"),
    )


def _format_row(row: _TableRow, widths: _ColumnWidths) -> str:
    """Render one body / header row with column padding."""
    agent_cell = row.agent.ljust(widths.agent + _TABLE_PADDING)
    event_cell = row.event.ljust(widths.event + _TABLE_PADDING)
    count_cell = row.count.rjust(widths.count)
    return "{0}{1}{2}".format(agent_cell, event_cell, count_cell)
