"""POSIX-only subprocess I/O helpers for e2e tests.

Uses select.select on file descriptors — not compatible with Windows.
"""

import os
import select
import time

_POLL_INTERVAL = 0.05
_READ_BUF_SIZE = 4096
_BUF_TAIL_LEN = 200


class ReadTimeout(Exception):
    """Raised when sentinel not seen within timeout."""

    def __init__(self, sentinel: str, timeout: float, buf: str) -> None:
        super().__init__(f"Sentinel {sentinel!r} not seen within {timeout}s. Buffer tail: {buf[-_BUF_TAIL_LEN:]!r}")
        self.buf = buf


class StreamEOF(Exception):
    """Raised when stream closes before sentinel is found."""

    def __init__(self, buf: str) -> None:
        super().__init__(f"Stream closed before sentinel was found. Buffer tail: {buf[-_BUF_TAIL_LEN:]!r}")
        self.buf = buf


def read_until(stream, sentinel: str, timeout: float) -> str:
    fd = stream.fileno()
    buf, deadline = "", time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], _POLL_INTERVAL)
        if ready:
            chunk = os.read(fd, _READ_BUF_SIZE)
            if not chunk:
                raise StreamEOF(buf)
            buf += chunk.decode("utf-8", errors="replace")
            if sentinel in buf:
                return buf
    raise ReadTimeout(sentinel, timeout, buf)


def send_line(stdin, text: str) -> None:
    stdin.write(f"{text}\n".encode("utf-8"))
    stdin.flush()
