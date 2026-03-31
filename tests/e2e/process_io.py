"""POSIX-only subprocess I/O helpers for e2e tests.

Uses select.select on file objects — not compatible with Windows.
"""

import select
import time

_POLL_INTERVAL = 0.05


def read_until(stream, sentinel: str, timeout: float) -> str:
    buf, deadline = "", time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([stream], [], [], _POLL_INTERVAL)
        if ready:
            chunk = stream.read(1)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            if sentinel in buf:
                break
    return buf


def send_line(stdin, text: str) -> None:
    stdin.write(f"{text}\n".encode("utf-8"))
    stdin.flush()
