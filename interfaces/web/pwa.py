"""PWA asset route handlers for the player web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse

_STATIC_DIR = Path(__file__).parent / "static"
_MANIFEST = _STATIC_DIR / "manifest.webmanifest"
_SERVICE_WORKER = _STATIC_DIR / "sw.js"


async def manifest() -> FileResponse:
    """Serve the PWA manifest from the top level for installability."""
    return FileResponse(_MANIFEST, media_type="application/manifest+json")


async def service_worker() -> FileResponse:
    """Serve the service worker from the top level so it can control the app shell."""
    return FileResponse(_SERVICE_WORKER, media_type="text/javascript")
