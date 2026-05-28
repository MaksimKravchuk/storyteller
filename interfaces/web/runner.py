"""Build a uvicorn ``Server`` for the player web UI.

Extracted so ``run_server.py`` can embed the web UI alongside the admin
dashboard without pulling ``uvicorn`` into its own import graph.
"""

from __future__ import annotations

import uvicorn

_WEB_HOST = "0.0.0.0"  # noqa: S104  # bind all interfaces inside the container
_WEB_APP_TARGET = "interfaces.web.app:app"


def build_web_server(port: int) -> uvicorn.Server:
    """Return a configured ``uvicorn.Server`` ready to ``await server.serve()``.

    Logging is intentionally left to the caller's loguru intercept handler
    (``log_config=None``) so the web UI's request lines flow through the
    same sink as the admin dashboard.
    """
    config = uvicorn.Config(
        _WEB_APP_TARGET,
        host=_WEB_HOST,
        port=port,
        log_config=None,
        access_log=False,
    )
    return uvicorn.Server(config)
