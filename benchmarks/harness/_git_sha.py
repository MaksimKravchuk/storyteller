"""Offline ``HEAD`` resolution — the harness does not shell out to ``git``."""

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


_GITDIR_MARKER = "gitdir:"


def _resolve_git_dir(git_path: Path) -> Path | None:
    """Return the real git directory, following a worktree ``.git`` pointer file.

    A linked worktree's ``.git`` is a file containing ``gitdir: <path>`` rather
    than a directory, so a plain ``.git/HEAD`` read misses it.
    """
    if git_path.is_dir():
        return git_path
    pointer = _read_text(git_path)
    if pointer is None or not pointer.strip().startswith(_GITDIR_MARKER):
        return None
    target = Path(pointer.strip()[len(_GITDIR_MARKER) :].strip())
    if target.is_absolute():
        return target
    return (git_path.parent / target).resolve()


def _common_git_dir(git_dir: Path) -> Path:
    """Return the shared dir that holds refs (``commondir`` for linked worktrees)."""
    common_text = _read_text(git_dir / "commondir")
    if common_text is None:
        return git_dir
    common = Path(common_text.strip())
    if common.is_absolute():
        return common
    return (git_dir / common).resolve()


def resolve_git_sha(git_path: Path) -> str:
    """Resolve HEAD's sha from a ``.git`` dir or worktree pointer; ``""`` on miss.

    Worktree-aware: HEAD lives in the worktree's git dir while its branch ref
    lives in the shared ``commondir``, so the two are resolved separately.
    """
    git_dir = _resolve_git_dir(git_path)
    if git_dir is None:
        return ""
    head_text = _read_text(git_dir / "HEAD")
    if head_text is None:
        return ""
    head_line = head_text.strip()
    if not head_line.startswith("ref:"):
        return head_line
    ref = head_line.split(" ", 1)[1].strip()
    return _resolve_ref(_common_git_dir(git_dir), ref)
