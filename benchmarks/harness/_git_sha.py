"""Offline ``HEAD`` resolution for ``current_git_sha`` in :mod:`archive`.

Reading ``.git/HEAD`` (and ``packed-refs``) directly keeps the benchmark
harness from shelling out to ``git``, so archives still record a SHA in
containers or tarballs where ``git`` is absent.
"""

from __future__ import annotations

from pathlib import Path

_ENCODING = "utf-8"


def _read_text(path: Path) -> str | None:
    """Read UTF-8 text from ``path``, returning ``None`` on I/O failure."""
    try:
        return path.read_text(encoding=_ENCODING)
    except OSError:
        return None


def _lookup_packed_ref(head_dir: Path, ref: str) -> str:
    """Find ``ref`` inside ``packed-refs``, returning empty string on miss."""
    packed_text = _read_text(head_dir / "packed-refs")
    if packed_text is None:
        return ""
    suffix = " {0}".format(ref)
    for line in packed_text.splitlines():
        if line.endswith(suffix):
            return line.split(" ", 1)[0]
    return ""


def _resolve_ref(head_dir: Path, ref: str) -> str:
    """Resolve one git ref by checking both loose and packed refs."""
    loose = _read_text(head_dir / ref)
    if loose is not None:
        return loose.strip()
    return _lookup_packed_ref(head_dir, ref)


def read_head_sha(head_file: Path) -> str:
    """Return the sha pointed at by ``head_file`` or ``""`` on any miss."""
    head_text = _read_text(head_file)
    if head_text is None:
        return ""
    head_line = head_text.strip()
    if head_line.startswith("ref:"):
        return _resolve_ref(head_file.parent, head_line.split(" ", 1)[1].strip())
    return head_line
